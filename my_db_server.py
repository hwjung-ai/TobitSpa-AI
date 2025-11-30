import json
import os
import sys
from mcp.server.fastmcp import FastMCP
import psycopg2
from neo4j import GraphDatabase

# 1. MCP 서버 이름 정의
mcp = FastMCP("MyDualDatabaseServer")

# ==========================================
# 2. 설정 파일 로드 (config/db_config.json)
# ==========================================
def load_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config", "db_config.json")
    
    try:
        # utf-8-sig로 인코딩 문제 해결
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            # 로그는 stderr로 출력해야 MCP 통신을 방해하지 않습니다.
            print(f"[Init] Loading config from: {config_path}", file=sys.stderr)
            return json.load(f)
    except Exception as e:
        print(f"[Error] Config Load Failed: {e}", file=sys.stderr)
        sys.exit(1)

config = load_config()
PG_CONFIG = config.get("postgres")
NEO_CONFIG = config.get("neo4j")

# ==========================================
# [NEW] 3. 접속 테스트 함수
# ==========================================
def test_connections():
    print("--- 🔌 Database Connection Test ---", file=sys.stderr)
    
    # 1) Postgres 테스트
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        conn.close()
        print("✅ Postgres: Connected Successfully!", file=sys.stderr)
    except Exception as e:
        print(f"❌ Postgres: Connection FAILED\n   Reason: {e}", file=sys.stderr)

    # 2) Neo4j 테스트
    try:
        uri = NEO_CONFIG.get("uri")
        auth = (NEO_CONFIG.get("user"), NEO_CONFIG.get("password"))
        driver = GraphDatabase.driver(uri, auth=auth)
        driver.verify_connectivity() # 연결 확인
        driver.close()
        print("✅ Neo4j   : Connected Successfully!", file=sys.stderr)
    except Exception as e:
        print(f"❌ Neo4j   : Connection FAILED\n   Reason: {e}", file=sys.stderr)
    
    print("-----------------------------------", file=sys.stderr)

# ==========================================
# 4. 도구 정의 (Postgres)
# ==========================================
@mcp.tool()
def query_postgres(sql_query: str) -> str:
    """PostgreSQL SELECT 쿼리 실행"""
    conn = None
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cur = conn.cursor()
        cur.execute(sql_query)
        
        if cur.description:
            columns = [desc[0] for desc in cur.description]
            results = cur.fetchall()
            if len(results) > 50:
                 return f"Columns: {columns}\n(Too many rows. First 50 shown)\n" + "\n".join([str(row) for row in results[:50]])
            output = f"Columns: {columns}\n"
            for row in results:
                output += f"{row}\n"
            return output
        else:
            conn.commit()
            return "Query executed successfully."
    except Exception as e:
        return f"Postgres Error: {str(e)}"
    finally:
        if conn: conn.close()

# ==========================================
# 5. 도구 정의 (Neo4j)
# ==========================================
@mcp.tool()
def query_neo4j(cypher_query: str) -> str:
    """Neo4j Cypher 쿼리 실행"""
    driver = None
    try:
        uri = NEO_CONFIG.get("uri")
        auth = (NEO_CONFIG.get("user"), NEO_CONFIG.get("password"))
        driver = GraphDatabase.driver(uri, auth=auth)
        
        def execute_tx(tx, query):
            result = tx.run(query)
            return [record.data() for record in result]

        with driver.session() as session:
            result_data = session.execute_read(execute_tx, cypher_query)
            return str(result_data)
    except Exception as e:
        return f"Neo4j Error: {str(e)}"
    finally:
        if driver: driver.close()

# ==========================================
# 6. 메인 실행
# ==========================================
if __name__ == "__main__":
    # 서버 시작 전에 연결 테스트 수행
    test_connections()
    # MCP 서버 시작 (여기서부터 Cline과 통신 대기)
    mcp.run()