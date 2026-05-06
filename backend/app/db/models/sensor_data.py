"""Sensor data ORM model exports."""
from app.db.base import Base
from app.models.sensor_data import SensorData

__all__ = ["Base", "SensorData"]
