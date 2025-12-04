from .asset import AssetDataSource, asset_ds_instance
from .metric import MetricDataSource
from .graph import GraphDataSource
from .manual_vector import ManualVectorSource
from .chat_history import ChatHistoryDataSource
from .work_history import WorkHistoryDataSource

# backward-compatibility shims required by api.py/tests
def _load_settings():
    """Return minimal settings dict used by api when running tests locally.
    Try to load real config.settings.SETTINGS if available, otherwise return a safe default.
    """
    try:
        from config.settings import SETTINGS  # type: ignore
        return SETTINGS
    except Exception:
        return {"postgres": {"host": "localhost", "port": 5432, "user": "postgres", "password": "", "dbname": "tobitspa"}}


def _compute_embedding(text: str):
    """Simple deterministic placeholder embedding for tests (small vector).
    Real implementation should call LLM/embedding provider.
    """
    # return a small fixed-dimension vector (list of floats)
    return [0.0]

__all__ = [
    "AssetDataSource",
    "asset_ds_instance",
    "MetricDataSource",
    "GraphDataSource",
    "ManualVectorSource",
    "ChatHistoryDataSource",
    "WorkHistoryDataSource",
    "_load_settings",
    "_compute_embedding",
]
