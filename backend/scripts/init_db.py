import psycopg
from psycopg import sql
import sys

def create_db():
    ports = [5433, 5432]
    passwords = ["password", "1sumitkumar"]
    
    success = False
    for port in ports:
        for pwd in passwords:
            conn_str = f"postgresql://postgres:{pwd}@localhost:{port}/postgres"
            try:
                print(f"Trying to connect to port {port} with password '{pwd}'...")
                conn = psycopg.connect(conn_str, autocommit=True)
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'legalmetrix'")
                    exists = cur.fetchone()
                    if not exists:
                        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier("legalmetrix")))
                        print(f"SUCCESS: Created database 'legalmetrix' on port {port}!")
                    else:
                        print(f"SUCCESS: Database 'legalmetrix' already exists on port {port}!")
                conn.close()
                print(f"WORKING_PORT={port}")
                print(f"WORKING_PWD={pwd}")
                success = True
                return port, pwd
            except Exception as e:
                print(f"Failed ({port}, {pwd}): {e}")
                
    if not success:
        print("Could not connect to postgres on any port/password combination.")
        sys.exit(1)

if __name__ == "__main__":
    create_db()
