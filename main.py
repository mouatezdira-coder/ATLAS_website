from flask import Flask, render_template, request, redirect, session, url_for, flash
import os
import db
from datetime import timedelta, datetime
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
load_dotenv()
# Création de l'application Flask
app = Flask(__name__)
app.secret_key = 'projet_thewave_secret'

# Fonction pour injecter les données utilisateur dans tous les templates
@app.context_processor
def inject_user_data():
    """Injecte l'or du joueur dans toutes les templates HTML si connecté."""
    if 'user_id' in session:
        user_data = execute_query("SELECT gold FROM joueur WHERE idj = %s", (session['user_id'],), fetch_one=True)
        if user_data:
            return {'user_gold': float(user_data[0])}
    return {'user_gold': 0.0}

# Durée de vie de la session permanente (60 minutes)
app.permanent_session_lifetime = timedelta(minutes=60)

# Fonction utilitaire pour exécuter des requêtes SQL
def execute_query(query, params=(), fetch_one=False):
    conn = db.connect() #connect à la base de données
    cur = conn.cursor()
    try:
        cur.execute(query, params)# execute la requete sql (demande les données)
        is_select = query.strip().upper().startswith('SELECT')
        has_returning = 'RETURNING' in query.upper()
        if is_select:
            result = cur.fetchone() if fetch_one else cur.fetchall() #(reponse de la demande)
        else:
            if has_returning:
                result = cur.fetchone() if fetch_one else cur.fetchall()
                #(reponse de la demande) si la requete contient un RETURNING, sinon None
            else:
                result = None
            conn.commit()
    except Exception as e:# en cas d'erreur, annule la transaction et affiche l'erreur
        conn.rollback()
        print(f"SQL Error: {e}")
        if query.strip().upper().startswith('SELECT'):
            result = None if fetch_one else []
        else:
            result = None
    finally:
        cur.close()#ferme la connexion à la base de données
        conn.close()#ferme la connexion à la base de données
    if query.strip().upper().startswith('SELECT') and not fetch_one:
        return result if result is not None else []#renvoi un resultat vide 
    return result


@app.route('/')
def home():
    # Affiche la page d'accueil
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']#récupère l'email du formulaire de connexion
        mdp = request.form['password']#récupère le mot de passe du formulaire de connexion
        user = execute_query("SELECT idj,pseudo, email, mot_de_passe FROM joueur WHERE email = %s", (email,), fetch_one=True)
        # Vérifie si l'utilisateur existe et si le mot de passe correspond
        if user and check_password_hash(user[3], mdp):#vérifie que le mot de passe hashé correspond à celui stocké dans la base de données
            session['user_id'] = user[0]
            session['pseudo'] = user[1]
            session['email'] = user[2]
            return redirect(url_for('home'))#redirige vers la page d'accueil après une connexion réussie
        flash("Identifiants incorrects", "error")
    return render_template('login.html')# si erreur reste sur la page de connexion

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            hashed_password = generate_password_hash(request.form['password'])
            sql = "INSERT INTO joueur (pseudo, email, mot_de_passe,date_naissance,date_inscription) VALUES (%s, %s, %s, %s, CURRENT_DATE)"
            execute_query(sql, (request.form['pseudo'], request.form['email'], hashed_password,request.form['date_naissance']))
            flash("Compte créé ! Connectez-vous.", "success")
            return redirect(url_for('login'))
        except:
            flash("Ce pseudo ou email existe déjà.", "error")
            
    return render_template('signup.html')

@app.route('/logout')
def logout():
    # Déconnexion de l'utilisateur
    session.clear()
    return redirect(url_for('login'))

from datetime import date  

@app.route('/profile')
@app.route('/profile/<int:user_id>')
def profile(user_id=None):
    if 'user_id' not in session: 
        return redirect(url_for('login'))
    
    # Si aucun user_id fourni, afficher le profil de l'utilisateur actuel
    if user_id is None:
        user_id = session['user_id']
    
    # Récupérer les informations de l'utilisateur
    user = execute_query(
        "SELECT idj, pseudo, email, date_naissance, date_inscription FROM joueur WHERE idj=%s", 
        (user_id,), 
        fetch_one=True
    )
    
    if not user:
        flash("Utilisateur non trouvé", "error")
        return redirect(url_for('home'))
    
    # Récupérer l'inventaire de l'utilisateur (objets qu'il possède)
    inventory = execute_query("""
        SELECT i.idi, i.nom, i.typei, i.rarity, inv.quantite, inv.dateAcquisition
        FROM inventory inv
        JOIN items i ON inv.idi = i.idi
        WHERE inv.idj = %s
        ORDER BY inv.dateAcquisition DESC
    """, (user_id,))
    
    # Récupérer les posts de l'utilisateur
    user_posts = execute_query("""
        SELECT idp, contenu, hashtags, post_date
        FROM post
        WHERE idj = %s
        ORDER BY post_date DESC
        LIMIT 20
    """, (user_id,))
    
    # Récupérer le nombre de followers
    followers = execute_query("""
        SELECT COUNT(*) as count FROM suivre WHERE idj2 = %s
    """, (user_id,), fetch_one=True)
    
    # Récupérer le nombre de following
    following = execute_query("""
        SELECT COUNT(*) as count FROM suivre WHERE idj1 = %s
    """, (user_id,), fetch_one=True)
    
    # Récupérer les groupes de l'utilisateur
    groups = execute_query("""
        SELECT g.idg, g.nom, g.topic
        FROM groupe g
        JOIN join_groupe jg ON g.idg = jg.idg
        WHERE jg.idj = %s
    """, (user_id,))
    
    # Vérifier si l'utilisateur actuel suit cet utilisateur
    is_following = False
    if session['user_id'] != user_id:
        follow_check = execute_query(
            "SELECT COUNT(*) FROM suivre WHERE idj1=%s AND idj2=%s",
            (session['user_id'], user_id),
            fetch_one=True
        )
        is_following = follow_check[0] > 0 if follow_check else False
    
    return render_template(
        'profile.html',
        user=user,
        inventory=inventory,
        user_posts=user_posts,
        followers=followers[0] if followers else 0,
        following=following[0] if following else 0,
        groups=groups,
        is_following=is_following,
        is_own_profile=(session['user_id'] == user_id)
    )

@app.route('/items/<int:item_id>')
def item_detail(item_id):
    # Récupérer les informations de l'item
    item = execute_query(
        "SELECT idi, nom, typei, rarity, dropZone, description FROM items WHERE idi=%s",
        (item_id,),
        fetch_one=True
    )
    avg_price = execute_query(
        "SELECT AVG(prix) FROM prix_histoire WHERE idi=%s",
        (item_id,),
        fetch_one=True
    )

    if not item:
        flash("Item non trouvé", "error")
        return redirect(url_for('items'))
    
    # Récupérer l'historique des prix de l'item
    price_history = execute_query("""
        SELECT prix, date_enregistrement
        FROM prix_histoire
        WHERE idi = %s
        ORDER BY date_enregistrement DESC
        LIMIT 30
    """, (item_id,))
    
    # Récupérer les annonces actives pour cet item
    listings = execute_query("""
        SELECT l.pk_listing, l.idj, j.pseudo, l.type_listing, l.quantite, l.prix_unitaire, l.date_creation
        FROM listings l
        JOIN joueur j ON l.idj = j.idj
        WHERE l.idi = %s AND l.status = 'actif'
        ORDER BY l.prix_unitaire ASC
    """, (item_id,))

    graph_labels = [p[1].strftime('%d/%m/%Y') for p in reversed(price_history) if p[1]]
    graph_values = [float(p[0]) for p in reversed(price_history)]

    
    
    return render_template(
        'item_detail.html',
        item=item,
        price_history=price_history,
        listings=listings,
        avg_price=avg_price[0] if avg_price and avg_price[0] is not None else 0.0,
        graph_labels=graph_labels,
        graph_values=graph_values
    )

@app.route('/posts')
def posts():
    # Get all posts with author info
    all_posts = execute_query("""
        SELECT p.idp, p.contenu, p.hashtags, p.post_date, j.idj, j.pseudo
        FROM post p
        JOIN joueur j ON p.idj = j.idj
        ORDER BY p.post_date DESC
        LIMIT 100
    """)
    
    return render_template('posts.html', posts=all_posts)

@app.route('/my_posts')
def my_posts():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_posts = execute_query("""
        SELECT p.idp, p.contenu, p.hashtags, p.post_date, j.idj, j.pseudo
        FROM post p
        JOIN joueur j ON p.idj = j.idj
        WHERE j.idj = %s
        ORDER BY p.post_date DESC
    """, (session['user_id'],))
    
    return render_template('my_posts.html', posts=user_posts)


@app.route('/create_post', methods=['GET', 'POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        contenu = request.form.get('contenu', '')
        hashtags = request.form.get('hashtags', '')
        
        if contenu:
            execute_query(
                "INSERT INTO post (contenu, hashtags, idj, post_date) VALUES (%s, %s, %s, CURRENT_DATE)",
                (contenu, hashtags, session['user_id'])
            )
            flash("Post créé avec succès!", "success")
            return redirect(url_for('posts'))
        else:
            flash("Le contenu du post ne peut pas être vide", "error")
    
    return render_template('create_post.html')

@app.route('/follow/<int:user_id>', methods=['POST'])
def follow_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_user = session['user_id']
    
    # Check if already following
    check = execute_query(
        "SELECT COUNT(*) FROM suivre WHERE idj1=%s AND idj2=%s",
        (current_user, user_id),
        fetch_one=True
    )
    
    if check and check[0] == 0:
        execute_query(
            "INSERT INTO suivre (idj1, idj2, dateFollowing) VALUES (%s, %s, CURRENT_DATE)",
            (current_user, user_id)
        )
        flash("Vous suivez maintenant cet utilisateur", "success")
    
    return redirect(url_for('profile', user_id=user_id))

@app.route('/unfollow/<int:user_id>', methods=['POST'])
def unfollow_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_user = session['user_id']
    
    execute_query(
        "DELETE FROM suivre WHERE idj1=%s AND idj2=%s",
        (current_user, user_id)
    )
    
    flash("Vous ne suivez plus cet utilisateur", "success")
    return redirect(url_for('profile', user_id=user_id))

@app.route('/items')
def items():
    # Récupération des paramètres de l'URL
    search_query = request.args.get('search', '')
    item_type = request.args.get('type', '')
    rarity_filter = request.args.get('rarity', '')

    # Construction dynamique de la requête SQL
    base_query = "SELECT idi, nom, typei, rarity, dropZone, description FROM items WHERE 1=1"
    params = []

    if search_query:
        # Recherche dans le nom ou la description
        base_query += " AND (nom ILIKE %s OR description ILIKE %s)"
        params.extend(['%' + search_query + '%', '%' + search_query + '%'])
    
    if item_type:
        base_query += " AND typei = %s"
        params.append(item_type)
    
    if rarity_filter:
        base_query += " AND rarity = %s"
        params.append(rarity_filter)
    
    base_query += " ORDER BY nom ASC"

    # Exécution de la requête filtrée
    all_items = execute_query(base_query, tuple(params))
    
    # Récupération des options pour les menus déroulants
    types = execute_query("SELECT DISTINCT typei FROM items ORDER BY typei")
    rarities = execute_query("SELECT DISTINCT rarity FROM items ORDER BY rarity")
    
    return render_template(
        'items.html',
        items=all_items,
        types=types,
        rarities=rarities,
        selected_type=item_type,
        selected_rarity=rarity_filter,
        search_query=search_query
    )

@app.route('/sell_item', methods=['POST'])
def sell_item():
    if 'user_id' not in session:
        flash("Vous devez être connecté pour vendre un item.", "error")
        return redirect(url_for('login'))

    user_id = session['user_id']
    item_id = request.form.get('item_id')
    
    try:
        quantity = int(request.form.get('quantity', 1))
        price = float(request.form.get('price', 0.0))
    except ValueError:
        flash("Valeurs invalides pour la quantité ou le prix.", "error")
        return redirect(url_for('profile'))

    if quantity <= 0 or price <= 0:
        flash("La quantité et le prix doivent être supérieurs à 0.", "error")
        return redirect(url_for('profile'))

    conn = db.connect()
    cur = conn.cursor()

    try:
        # Début de la transaction
        cur.execute("BEGIN")

        # 1. Vérifier si le joueur possède l'item et la bonne quantité
        cur.execute("SELECT quantite FROM inventory WHERE idj = %s AND idi = %s FOR UPDATE", (user_id, item_id))
        inv = cur.fetchone()

        if not inv or inv[0] < quantity:
            flash("Vous ne possédez pas assez de cet item.", "error")
            cur.execute("ROLLBACK")
            return redirect(url_for('profile'))

        # 2. Retirer l'item de l'inventaire du vendeur
        cur.execute("UPDATE inventory SET quantite = quantite - %s WHERE idj = %s AND idi = %s", (quantity, user_id, item_id))
        
        # Nettoyer l'inventaire si la quantité tombe à 0
        cur.execute("DELETE FROM inventory WHERE quantite <= 0")

        # 3. Créer l'annonce (listing) sur le marché
        cur.execute("""
            INSERT INTO listings (idj, idi, type_listing, quantite, prix_unitaire, status, date_creation)
            VALUES (%s, %s, 'vente', %s, %s, 'actif', CURRENT_TIMESTAMP)
        """, (user_id, item_id, quantity, price))

        cur.execute("COMMIT")
        flash("Votre annonce a été publiée avec succès sur le marché !", "success")

    except Exception as e:
        cur.execute("ROLLBACK")
        flash("Une erreur est survenue lors de la mise en vente.", "error")
        print(f"Sell Error: {e}")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('profile'))
@app.route('/discussions',methods=['GET','POST'])
def discussions():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
    list_receivers = execute_query("SELECT DISTINCT receiver,pseudo FROM discussion join joueur on discussion.receiver = joueur.idj WHERE discussion.sender = %s", (session['user_id'],))
    possible_receivers = execute_query("SELECT idj, pseudo FROM joueur WHERE idj != %s", (session['user_id'],))
    if request.method == 'POST':    
        receiver_id = request.form.get('receiver_id')
        contenu = request.form.get('message', '')
    if request.method == 'POST':
        selected_receiver_id = request.form.get('receiver_id')
        if contenu and receiver_id:
            execute_query("""
                INSERT INTO discussion (sender, receiver, contenu) 
                VALUES (%s, %s, %s)
            """, (session['user_id'], receiver_id, contenu))
            flash("Message envoyé !", "success")
        else:
            flash("Le message ne peut pas être vide.", "error")
        if selected_receiver_id:
            return redirect(url_for('discussion', receiver_id=selected_receiver_id))
        
    return render_template('discussions.html',list_receivers=list_receivers, possible_receivers=possible_receivers)
@app.route('/discussion/<int:receiver_id>', methods=['GET', 'POST'])
def discussion(receiver_id):
    
    if 'user_id' not in session:
        flash("Vous devez être connecté pour accéder aux discussions.", "error")
        return redirect(url_for('login'))
    else:
        messages = execute_query("""
            SELECT d.contenu, d.date_sent, j.pseudo
            FROM discussion d
            JOIN joueur j ON d.sender = j.idj
            WHERE (d.sender = %s AND d.receiver = %s) OR (d.sender = %s AND d.receiver = %s)
            ORDER BY d.date_sent DESC
    """, (session['user_id'], receiver_id, receiver_id, session['user_id']))
        receiver_name = execute_query("SELECT pseudo FROM joueur WHERE idj = %s", (receiver_id,), fetch_one=True)

        return render_template('discussion.html', messages=messages, receiver_name=receiver_name,receiver_id=receiver_id)
@app.route('/send_message/<int:receiver_id>', methods=['POST'])
def send_message(receiver_id):
    if 'user_id' not in session:
        flash("Vous devez être connecté pour envoyer un message.", "error")
        return redirect(url_for('login'))
    contenu = request.form.get('message', '')
    if contenu:
        execute_query("""
            INSERT INTO discussion (sender, receiver, contenu) 
            VALUES (%s, %s, %s)
        """, (session['user_id'], receiver_id, contenu))
        flash("Message envoyé !", "success")
    else:
        flash("Le message ne peut pas être vide.", "error")
    return redirect(url_for('discussion', receiver_id=receiver_id))
@app.route('/buy_item/<int:listing_id>', methods=['POST'])
def buy_item(listing_id):
    if 'user_id' not in session:
        flash("Vous devez être connecté pour acheter un item.", "error")
        return redirect(url_for('login'))

    buyer_id = session['user_id']
    
    conn = db.connect()
    cur = conn.cursor()

    try:
        cur.execute("BEGIN")

        # 1. Verrouiller l'annonce pour éviter les achats simultanés
        cur.execute("""
            SELECT idj, idi, quantite, prix_unitaire, status 
            FROM listings 
            WHERE pk_listing = %s FOR UPDATE
        """, (listing_id,))
        listing = cur.fetchone()

        if not listing or listing[4] != 'actif':
            flash("Cette annonce n'est plus disponible.", "error")
            cur.execute("ROLLBACK")
            return redirect(request.referrer or url_for('items'))

        seller_id, item_id, quantity, price_unit = listing[0], listing[1], listing[2], listing[3]
        total_price = quantity * price_unit

        # 2. Empêcher d'acheter son propre item
        if buyer_id == seller_id:
            flash("Vous ne pouvez pas acheter votre propre item.", "error")
            cur.execute("ROLLBACK")
            return redirect(request.referrer or url_for('items'))

        # 3. Vérifier si l'acheteur a assez d'or
        cur.execute("SELECT gold FROM joueur WHERE idj = %s FOR UPDATE", (buyer_id,))
        buyer_gold = cur.fetchone()[0]

        if buyer_gold < total_price:
            flash("Vous n'avez pas assez d'or pour cet achat.", "error")
            cur.execute("ROLLBACK")
            return redirect(request.referrer or url_for('items'))

        # 4. Transfert d'or
        cur.execute("UPDATE joueur SET gold = gold - %s WHERE idj = %s", (total_price, buyer_id))
        cur.execute("UPDATE joueur SET gold = gold + %s WHERE idj = %s", (total_price, seller_id))

        # 5. Transfert de l'Item
        cur.execute("SELECT quantite FROM inventory WHERE idj = %s AND idi = %s", (buyer_id, item_id))
        inv = cur.fetchone()

        if inv:
            cur.execute("UPDATE inventory SET quantite = quantite + %s WHERE idj = %s AND idi = %s", (quantity, buyer_id, item_id))
        else:
            cur.execute("INSERT INTO inventory (idj, idi, quantite) VALUES (%s, %s, %s)", (buyer_id, item_id, quantity))

        # 6. Marquer l'annonce comme terminée
        cur.execute("UPDATE listings SET status = 'completé' WHERE pk_listing = %s", (listing_id,))

        # 7. Historique et Graphique de prix
        cur.execute("""
            INSERT INTO transactions (acheteur_id, vendeur_id, idi, quantite, prix_total) 
            VALUES (%s, %s, %s, %s, %s)
        """, (buyer_id, seller_id, item_id, quantity, total_price))

        cur.execute("""
            INSERT INTO prix_histoire (idi, prix) VALUES (%s, %s)
        """, (item_id, price_unit))

        cur.execute("COMMIT")
        flash(f"Achat réussi ! Vous avez dépensé {total_price} gold.", "success")

    except Exception as e:
        cur.execute("ROLLBACK")
        flash("Une erreur est survenue lors de l'achat.", "error")
        print(f"Buy Error: {e}")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('item_detail', item_id=item_id))
if __name__ == '__main__':
    app.run(debug=True)
