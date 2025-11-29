import psycopg2
from neo4j import GraphDatabase

def check_postgres():
    conn = psycopg2.connect(
        host="115.21.12.151",
        port=5432,
        dbname="spadb",
        user="spa",
        password="spa1!",
        connect_timeout=5,
    )
    with conn, conn.cursor() as cur:
        cur.execute("SELECT 1;")
        cur.fetchone()
    conn.close()

def check_neo4j():
    driver = GraphDatabase.driver(
        "bolt://115.21.12.151:7687",
        auth=("neo4j", "wemb1!"),
        connection_timeout=5,
    )
    with driver.session() as session:
        session.run("RETURN 1;").single()
    driver.close()

if __name__ == "__main__":
    try:
        check_postgres()
        check_neo4j()
        print("정상")
    except Exception as e:
        print("오류:", e)
