import os

# 必须在任何 app 模块导入前生效：测试用内存 SQLite，不连 Postgres
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SEED_ON_EMPTY"] = "true"
