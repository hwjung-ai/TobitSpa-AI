# -*- coding: utf-8 -*-
import psycopg2
import json
import os
import random
from datetime import datetime, timedelta
from neo4j import GraphDatabase

# --- Configuration ---
def _load_full_config():
    """config/db_config.json 파일에서 전체 설정을 읽어옵니다."""
    config_path = os.getenv("APP_CONFIG_PATH", os.path.join("config", "db_config.json"))
    if not os.path.exists(config_path):
        print(f"경고: 설정 파일 '{config_path}'을(를) 찾을 수 없습니다. 기본값을 사용합니다.")
        return {"postgres": {}, "neo4j": {}}
    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as e:
        print(f"경고: 설정 파일 로드 실패. 기본값을 사용합니다. 오류: {e}")
        return {"postgres": {}, "neo4j": {}}

FULL_CONFIG = _load_full_config()

def get_db_connection():
    """PostgreSQL 데이터베이스 연결 객체를 반환합니다."""
    pg_defaults = {"host": "localhost", "port": 5432, "dbname": "spadb", "user": "spa", "password": "password"}
    pg_config = FULL_CONFIG.get("postgres", {})
    pg_defaults.update(pg_config)
    
    try:
        conn = psycopg2.connect(**pg_defaults)
        print("PostgreSQL 데이터베이스 연결 성공.")
        return conn
    except psycopg2.OperationalError as e:
        print(f"오류: PostgreSQL에 연결할 수 없습니다. 연결 설정을 확인하세요: {e}")
        return None

def get_neo4j_driver():
    """Neo4j 데이터베이스 드라이버를 반환합니다."""
    neo4j_defaults = {"uri": "neo4j://localhost:7687", "user": "neo4j", "password": "password"}
    neo4j_config = FULL_CONFIG.get("neo4j", {})
    neo4j_defaults.update(neo4j_config)
    
    try:
        driver = GraphDatabase.driver(neo4j_defaults["uri"], auth=(neo4j_defaults["user"], neo4j_defaults["password"]))
        driver.verify_connectivity()
        print("Neo4j 데이터베이스 연결 성공.")
        return driver
    except Exception as e:
        print(f"오류: Neo4j에 연결할 수 없습니다. 연결 설정을 확인하세요: {e}")
        return None

# --- Sample Data ---

# 1. Assets (자산)
ASSETS_DATA = [
    {"asset_type": "IT_DEVICE", "name": "web-server-01", "attributes": {"ip": "192.168.1.10", "os": "Ubuntu 22.04 LTS"}},
    {"asset_type": "IT_DEVICE", "name": "db-server-01", "attributes": {"ip": "192.168.1.11", "os": "Rocky Linux 9"}},
    {"asset_type": "IT_DEVICE", "name": "core-switch-01", "attributes": {"ip": "192.168.1.1", "model": "Cisco Catalyst 9300"}},
    {"asset_type": "APPLICATION", "name": "ERP-System", "attributes": {"url": "http://erp.internal.corp", "language": "Java"}},
    {"asset_type": "APPLICATION", "name": "Analytics-Platform", "attributes": {"url": "http://analytics.internal.corp", "language": "Python"}},
]

# 2. Work History & Maintenance (작업 이력 및 유지보수)
WORK_HISTORY_DATA = [
    {"asset_name": "web-server-01", "work_date": datetime.now() - timedelta(days=10), "worker_name": "Alice", "work_type": "update", "description": "Apache 웹 서버 보안 패치 (v2.4.54)"},
    {"asset_name": "db-server-01", "work_date": datetime.now() - timedelta(days=25), "worker_name": "Bob", "work_type": "maintenance", "description": "PostgreSQL 데이터베이스 정기 백업 및 인덱스 재구성"},
    {"asset_name": "web-server-01", "work_date": datetime.now() - timedelta(days=40), "worker_name": "Alice", "work_type": "install", "description": "SSL 인증서 갱신"},
    {"asset_name": "core-switch-01", "work_date": datetime.now() - timedelta(days=60), "worker_name": "Charlie", "work_type": "config", "description": "VLAN 20 (Guest) 포트 설정 변경"}
]
MAINTENANCE_DATA = [
    {"asset_name": "db-server-01", "work_date": datetime.now() - timedelta(days=5), "worker_name": "David", "work_type": "security", "description": "DB 접근 제어 목록(ACL) 검토 및 업데이트"},
    {"asset_name": "Analytics-Platform", "work_date": datetime.now() - timedelta(days=15), "worker_name": "Eve", "work_type": "update", "description": "Dask 라이브러리 v2023.10.0으로 업그레이드"},
]
WORK_HISTORY_DATA.extend(MAINTENANCE_DATA)

# 3. Events (이벤트)
EVENTS_DATA = [
    {"asset_name": "web-server-01", "event_time": datetime.now() - timedelta(hours=2), "severity": "INFO", "event_type": "login", "description": "User 'admin' logged in from 10.0.0.5"},
    {"asset_name": "db-server-01", "event_time": datetime.now() - timedelta(minutes=90), "severity": "WARNING", "event_type": "disk_space", "description": "Disk usage on /var/lib/pgsql is at 85%"},
]

# 4. Chat History (채팅 이력)
CHAT_HISTORY_DATA = [
    {"session_id": "sample-session-123", "role": "user", "content": "web-server-01의 OS 버전을 알려주세요."},
    {"session_id": "sample-session-123", "role": "assistant", "content": "web-server-01의 OS는 Ubuntu 22.04 LTS 입니다."},
]

# 5. Metrics (시계열 수치)
METRICS_DATA = []
now = datetime.now()
for i in range(60): # 1시간 분량 데이터
    ts = now - timedelta(minutes=i)
    METRICS_DATA.append({"asset_name": "web-server-01", "ts": ts, "metric": "cpu_usage", "value": random.uniform(15, 40)})
    METRICS_DATA.append({"asset_name": "db-server-01", "ts": ts, "metric": "cpu_usage", "value": random.uniform(30, 75)})

# 6. Graph Relationships (그래프 관계)
RELATIONSHIPS_DATA = [
    {"source": "ERP-System", "target": "web-server-01", "type": "RUNS_ON"},
    {"source": "Analytics-Platform", "target": "web-server-01", "type": "RUNS_ON"},
    {"source": "ERP-System", "target": "db-server-01", "type": "CONNECTS_TO"},
    {"source": "web-server-01", "target": "core-switch-01", "type": "CONNECTED_TO"},
    {"source": "db-server-01", "target": "core-switch-01", "type": "CONNECTED_TO"},
]

# --- Data Insertion Functions ---

def setup_timescaledb(cursor):
    """TimescaleDB 확장 및 하이퍼테이블 설정을 처리합니다."""
    print("TimescaleDB 설정 확인 및 적용 중...")
    cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    cursor.execute("SELECT create_hypertable('metrics', 'ts', if_not_exists => TRUE, migrate_data => TRUE)")
    cursor.execute("SELECT create_hypertable('events', 'event_time', if_not_exists => TRUE, migrate_data => TRUE)")
    print("TimescaleDB 설정 완료.")

def clear_pg_tables(cursor):
    """PostgreSQL 테이블의 모든 데이터를 삭제합니다."""
    print("PostgreSQL 테이블 데이터 삭제 중...")
    cursor.execute("TRUNCATE TABLE chat_history, work_history, assets RESTART IDENTITY CASCADE")
    cursor.execute("TRUNCATE TABLE events, metrics")
    print("PostgreSQL 테이블 데이터 삭제 완료.")

def insert_assets(cursor, assets):
    print(f"{len(assets)}개의 자산 데이터 삽입 중...")
    asset_name_to_id = {}
    query = "INSERT INTO assets (asset_type, name, attributes) VALUES (%s, %s, %s) RETURNING id, name"
    for asset in assets:
        cursor.execute(query, (asset['asset_type'], asset['name'], json.dumps(asset['attributes'])))
        asset_id, asset_name = cursor.fetchone()
        asset_name_to_id[asset_name] = asset_id
    print("자산 데이터 삽입 완료.")
    return asset_name_to_id

def insert_work_history(cursor, work_items, asset_map):
    print(f"{len(work_items)}개의 작업 이력 데이터 삽입 중...")
    query = "INSERT INTO work_history (asset_id, work_date, worker_name, work_type, description) VALUES (%s, %s, %s, %s, %s)"
    for item in work_items:
        asset_id = asset_map.get(item['asset_name'])
        if asset_id:
            cursor.execute(query, (asset_id, item['work_date'], item['worker_name'], item['work_type'], item['description']))
    print("작업 이력 데이터 삽입 완료.")

def insert_events(cursor, events, asset_map):
    print(f"{len(events)}개의 이벤트 데이터 삽입 중...")
    query = "INSERT INTO events (asset_id, event_time, severity, event_type, description) VALUES (%s, %s, %s, %s, %s)"
    for event in events:
        asset_id = asset_map.get(event['asset_name'])
        if asset_id:
            cursor.execute(query, (asset_id, event['event_time'], event['severity'], event['event_type'], event['description']))
    print("이벤트 데이터 삽입 완료.")
    
def insert_metrics(cursor, metrics, asset_map):
    print(f"{len(metrics)}개의 메트릭 데이터 삽입 중...")
    query = "INSERT INTO metrics (asset_id, ts, metric, value) VALUES (%s, %s, %s, %s)"
    for metric_item in metrics:
        asset_id = asset_map.get(metric_item['asset_name'])
        if asset_id:
            cursor.execute(query, (asset_id, metric_item['ts'], metric_item['metric'], metric_item['value']))
    print("메트릭 데이터 삽입 완료.")

def insert_chat_history(cursor, chats):
    print(f"{len(chats)}개의 채팅 이력 데이터 삽입 중...")
    query = "INSERT INTO chat_history (session_id, role, content) VALUES (%s, %s, %s)"
    for chat in chats:
        cursor.execute(query, (chat['session_id'], chat['role'], chat['content']))
    print("채팅 이력 데이터 삽입 완료.")

def seed_neo4j_data(driver, assets, relationships):
    """Neo4j 데이터베이스에 노드와 관계를 시딩합니다."""
    print("Neo4j 데이터 시딩 시작...")
    with driver.session() as session:
        # 1. 기존 데이터 삭제
        print("기존 Neo4j 데이터 삭제 중...")
        session.run("MATCH (n) DETACH DELETE n")
        
        # 2. 노드 생성
        print(f"{len(assets)}개의 노드 생성 중...")
        for asset in assets:
            # asset_type을 Label로 사용, name을 식별자로 사용
            cypher = f"CREATE (a:{asset['asset_type']} {{name: $name, attributes: $attributes}})"
            session.run(cypher, name=asset['name'], attributes=json.dumps(asset['attributes']))
        
        # 3. 관계 생성
        print(f"{len(relationships)}개의 관계 생성 중...")
        for rel in relationships:
            cypher = """
            MATCH (a {name: $source_name}), (b {name: $target_name})
            CREATE (a)-[:""" + rel['type'] + """]->(b)
            """
            session.run(cypher, source_name=rel['source'], target_name=rel['target'])
    print("Neo4j 데이터 시딩 완료.")


def main():
    """메인 실행 함수"""
    pg_conn = get_db_connection()
    neo4j_driver = get_neo4j_driver()

    if not pg_conn or not neo4j_driver:
        print("데이터베이스 연결에 실패하여 시딩을 중단합니다.")
        if pg_conn: pg_conn.close()
        if neo4j_driver: neo4j_driver.close()
        return

    try:
        # --- PostgreSQL 시딩 ---
        with pg_conn.cursor() as cursor:
            print("\n--- PostgreSQL 데이터 시딩 시작 ---")
            clear_pg_tables(cursor)
            setup_timescaledb(cursor)
            
            asset_map = insert_assets(cursor, ASSETS_DATA)
            insert_work_history(cursor, WORK_HISTORY_DATA, asset_map)
            insert_events(cursor, EVENTS_DATA, asset_map)
            insert_metrics(cursor, METRICS_DATA, asset_map)
            insert_chat_history(cursor, CHAT_HISTORY_DATA)
            
            pg_conn.commit()
            print("--- PostgreSQL 데이터 시딩 완료 ---\n")

        # --- Neo4j 시딩 ---
        seed_neo4j_data(neo4j_driver, ASSETS_DATA, RELATIONSHIPS_DATA)
        
        print("\n✅ 모든 샘플 데이터가 성공적으로 삽입되었습니다.")
        
    except Exception as e:
        print(f"\n❌ 오류가 발생했습니다: {e}")
        if pg_conn: pg_conn.rollback()
    finally:
        if pg_conn: pg_conn.close()
        if neo4j_driver: neo4j_driver.close()
        print("모든 데이터베이스 연결이 종료되었습니다.")

if __name__ == "__main__":
    main()
