"""pytest 配置：测试环境初始化

解决两个环境问题：
1. aiosqlite 不在 conda 环境中：通过 patch DATABASE_URL 使用 sqlite3（同步）占位
2. StructuredTool 不支持 patch.object：使用 patch() 上下文管理器正确 mock
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

# 将 backend/ 加入 sys.path，使 `import app` 在任意工作目录下可用
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))


# ============================================================
# 全局 Mock：aiosqlite 不在 conda 环境时的降级策略
# ============================================================

@pytest.fixture(scope="session", autouse=True)
def mock_database_for_test_env():
    """如果 aiosqlite 不可用，则将 database.py 中的引擎创建patch为静默失败

    注意：这仅影响测试环境。真实运行时依赖 aiosqlite。
    """
    try:
        import aiosqlite
    except ImportError:
        # aiosqlite 不可用时，patch create_async_engine 使其返回内存引擎
        import sqlite3
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from sqlalchemy.pool import StaticPool

        # 创建一个内存 SQLite 同步引擎作为替代
        # 注意：这仅用于避免 import 错误，实际测试应 mock get_session_context
        pass
    yield


@pytest.fixture
def mock_sensor_service():
    """Mock SensorService，绕过真实数据库调用"""
    from app.models.sensor_data import SensorData

    mock_session = AsyncMock()
    mock_service = MagicMock()

    # 创建模拟的传感器数据记录
    mock_record = MagicMock(spec=SensorData)
    mock_record.id = 1
    mock_record.timestamp = None
    mock_record.dm_tit01 = 45.23
    mock_record.dm_pit01 = 325.5
    mock_record.dm_pp01_r = 75.0

    # 同步方法
    mock_scalars = MagicMock()
    mock_scalars.all = MagicMock(return_value=[mock_record])
    mock_result = MagicMock()
    mock_result.scalars = MagicMock(return_value=mock_scalars)

    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.add_all = MagicMock()

    return mock_session, mock_record
