import psycopg2
import os
def connect():
    try:
        conn = psycopg2.connect(
            # On récupère les infos depuis les variables d'environnement
            host=os.environ.get("DB_HOST"),
            database="postgres",
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            port="6543",
            sslmode="require"  # Très important pour le cloud !
        )
        return conn
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        return None
