# File: scripts/init_db.py
"""数据库初始化与数据导入脚本

功能：
1. 通过 Alembic 迁移创建数据库表
2. 将 HAI 数据集 CSV 文件分块读取并导入

使用方式（在仓库根目录或 backend 目录执行均可；默认 CSV 指向仓库 datasets/）:
    python scripts/init_db.py
    python scripts/init_db.py --csv-path ../datasets/haiend-23.05/end-test1.csv
    python scripts/init_db.py --csv-path ../datasets/haiend-23.05/end-test1.csv --chunk-size 5000
"""
import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

# 添加项目根目录到导入路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from app.db.models.sensor_data import SensorData
from app.db.session import get_engine, get_session_context

if TYPE_CHECKING:
    import pandas as pd


# CSV 列名到模型字段名的映射（CSV列名 -> 模型字段名）
# 只包含需要从 extra_sensors 提取的核心字段，不在此列表中的列都归入 extra_sensors
CORE_COLUMN_MAPPING: dict[str, str] = {
    # 直接映射（列名与字段名一致）
    "DM-PP01-R": "dm_pp01_r",
    "DM-FT01Z": "dm_ft01z",
    "DM-FT02Z": "dm_ft02z",
    "DM-FT03Z": "dm_ft03z",
    "DM-PP01A-D": "dm_pp01a_d",
    "DM-PP01A-R": "dm_pp01a_r",
    "DM-PP04-D": "dm_pp04_d",
    "DM-PP04-AO": "dm_pp04_ao",
    "DM-FT01": "dm_ft01",
    "DM-FT02": "dm_ft02",
    "DM-FT03": "dm_ft03",
    "DM-TIT01": "dm_tit01",
    "DM-TIT02": "dm_tit02",
    "DM-PIT01": "dm_pit01",
    "DM-PIT01-HH": "dm_pit01_hh",
    "DM-PIT02": "dm_pit02",
    "DM-LIT01": "dm_lit01",
    "DM-LCV01-D": "dm_lcv01_d",
    "DM-LCV01-Z": "dm_lcv01_z",
    "DM-FCV01-D": "dm_fcv01_d",
    "DM-FCV01-Z": "dm_fcv01_z",
    "DM-FCV02-D": "dm_fcv02_d",
    "DM-FCV02-Z": "dm_fcv02_z",
    "DM-FCV03-D": "dm_fcv03_d",
    "DM-FCV03-Z": "dm_fcv03_z",
    "DM-PCV01-D": "dm_pcv01_d",
    "DM-PCV01-Z": "dm_pcv01_z",
    "DM-PCV01-DEV": "dm_pcv01_dev",
    "DM-PCV02-D": "dm_pcv02_d",
    "DM-PCV02-Z": "dm_pcv02_z",
    "DM-AIT-DO": "dm_ait_do",
    "DM-AIT-PH": "dm_ait_ph",
    "DM-SOL01-D": "dm_sol01_d",
    "DM-SOL02-D": "dm_sol02_d",
    "DM-SOL03-D": "dm_sol03_d",
    "DM-SOL04-D": "dm_sol04_d",
    "DM-LSH-03": "dm_lsh_03",
    "DM-LSH-04": "dm_lsh_04",
    "DM-LSL-04": "dm_lsl_04",
    "DM-LSH01": "dm_lsh01",
    "DM-LSH02": "dm_lsh02",
    "DM-LSL01": "dm_lsl01",
    "DM-LSL02": "dm_lsl02",
    "DM-CIP-1ST": "dm_cip_1st",
    "DM-CIP-2ND": "dm_cip_2nd",
    "DM-CIP-START": "dm_cip_start",
    "DM-CIP-STEP1": "dm_cip_step1",
    "DM-CIP-STEP11": "dm_cip_step11",
    "DM-CIPH-1ST": "dm_ciph_1st",
    "DM-CIPH-2ND": "dm_ciph_2nd",
    "DM-CIPH-START": "dm_ciph_start",
    "DM-CIPH-STEP1": "dm_ciph_step1",
    "DM-CIPH-STEP11": "dm_ciph_step11",
    "DM-COOL-ON": "dm_cool_on",
    "DM-COOL-R": "dm_cool_r",
    "DM-HT01-D": "dm_ht01_d",
    "DM-TWIT-03": "dm_twit_03",
    "DM-TWIT-04": "dm_twit_04",
    "DM-TWIT-05": "dm_twit_05",
    "DM-PWIT-03": "dm_pwit_03",
    "DM-SS01-RM": "dm_ss01_rm",
    "DM-ST-SP": "dm_st_sp",
    "DM-SW01-ST": "dm_sw01_st",
    "DM-SW02-SP": "dm_sw02_sp",
    "DM-SW03-EM": "dm_sw03_em",
    "GATEOPEN": "gate_open",
    "PP04-SP-OUT": "pp04_sp_out",
    "DQ03-LCV01-D": "dq03_lcv01_d",
    "DQ04-LCV01-DEV": "dq04_lcv01_dev",
}

# 模型中的所有核心字段名集合
CORE_FIELDS: set[str] = set(CORE_COLUMN_MAPPING.values())

MISSING_DB_DRIVER_MESSAGE = """错误: 当前 Python 环境缺少数据库驱动依赖: {driver}

请先使用项目虚拟环境，或安装 requirements.txt 中的依赖后再重试。

推荐命令:
  .\\venv\\Scripts\\python.exe scripts/init_db.py --init-only

如果还没有安装依赖:
  pip install -r requirements.txt
"""

MISSING_PANDAS_MESSAGE = """错误: 当前 Python 环境缺少 CSV 导入依赖: pandas

如果你只是初始化数据库，请直接运行:
  python scripts/init_db.py --init-only

如果你还需要导入 CSV，请先安装依赖:
  pip install -r requirements.txt

或使用项目虚拟环境:
  ./venv/bin/python scripts/init_db.py --csv-path <your_csv_path>
"""


def parse_timestamp(ts_str: str) -> datetime:
    """解析 CSV 中的时间戳字符串"""
    return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")


def dataframe_to_records(df: Any) -> list[dict]:
    """将 DataFrame 行转换为 ORM 记录字典列表

    Args:
        df: 读取的 CSV DataFrame

    Returns:
        字典列表，每字典对应一条 SensorData 记录
    """
    records = []
    core_fields = CORE_FIELDS

    for _, row in df.iterrows():
        record = {"timestamp": parse_timestamp(row["Timestamp"])}

        # 分离核心字段和扩展字段
        extra_sensors = {}
        for col in df.columns:
            if col == "Timestamp":
                continue

            # 检查是否是核心字段
            model_field = CORE_COLUMN_MAPPING.get(col)
            if model_field and model_field in core_fields:
                record[model_field] = row[col]
            else:
                # 扩展传感器存入 JSON
                extra_sensors[col] = row[col]

        # 只有当有扩展传感器时才添加 extra_sensors 字段
        if extra_sensors:
            record["extra_sensors"] = extra_sensors

        records.append(record)

    return records


def init_database():
    """通过 Alembic 创建数据库表.

    Alembic 的 env.py 会自行管理异步迁移生命周期，这里必须保持同步调用，
    否则会在已经运行的事件循环里再次触发 asyncio.run()。
    """
    print("正在执行数据库迁移...")

    alembic_cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(alembic_cfg, "head")

    print("数据库迁移完成。")


async def import_csv(csv_path: str, chunk_size: int = 5000):
    """分块读取 CSV 并导入数据库

    Args:
        csv_path: CSV 文件路径
        chunk_size: 每块读取的行数（默认 5000）
    """
    engine = get_engine()
    total_imported = 0

    print(f"开始导入 CSV 文件: {csv_path}")
    print(f"分块大小: {chunk_size}")

    # 验证文件存在
    if not Path(csv_path).exists():
        print(f"错误: 文件不存在 - {csv_path}")
        return

    try:
        try:
            import pandas as pd
        except ModuleNotFoundError as exc:
            if exc.name == "pandas":
                raise SystemExit(MISSING_PANDAS_MESSAGE) from exc
            raise

        # 分块读取 CSV
        for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunk_size)):
            # 转换为记录格式
            records = dataframe_to_records(chunk)

            # 批量插入
            async with get_session_context() as session:
                from sqlalchemy import insert
                stmt = insert(SensorData)
                await session.execute(stmt, records)
                # session 由 context manager 自动提交

            chunk_count = len(records)
            total_imported += chunk_count
            print(f"  块 {i+1}: 已导入 {chunk_count} 条记录 (累计: {total_imported})")

    except Exception as e:
        print(f"导入过程中出错: {e}")
        raise
    finally:
        await engine.dispose()

    print(f"\n导入完成! 总计导入 {total_imported} 条记录。")


def main():
    """命令行入口"""
    _repo_root = Path(__file__).resolve().parents[2]
    _default_csv = _repo_root / "datasets" / "haiend-23.05" / "end-test1.csv"
    parser = argparse.ArgumentParser(description="初始化数据库并导入 HAI 数据集")
    parser.add_argument(
        "--csv-path",
        type=str,
        default=str(_default_csv),
        help="CSV 文件路径"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=5000,
        help="每块读取的行数 (默认: 5000)"
    )
    parser.add_argument(
        "--init-only",
        action="store_true",
        help="仅初始化数据库表，不导入数据"
    )

    args = parser.parse_args()

    try:
        # 初始化数据库表
        init_database()

        # 导入数据（如果指定）
        if not args.init_only:
            asyncio.run(import_csv(args.csv_path, args.chunk_size))
    except ModuleNotFoundError as exc:
        if exc.name in {"aiosqlite", "asyncpg"}:
            raise SystemExit(
                MISSING_DB_DRIVER_MESSAGE.format(driver=exc.name)
            ) from exc
        raise


if __name__ == "__main__":
    main()
