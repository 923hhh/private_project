# File: app/models/sensor_data.py
"""SQLAlchemy ORM models for sensor data.

Storage Strategy: Hybrid Approach
- Core indexed fields: id, timestamp, primary sensors (for efficient querying)
- Extended sensors: JSON column for auxiliary tags (flexibility for schema changes)
- Rationale: Balances query performance with schema evolution needs

HAI Dataset Analysis:
- ~170 sensor columns per timestamp
- Mix of binary valves/switches and continuous measurements (temp, pressure, flow)
- Primary sensors (DM-*) represent critical device measurements
"""
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SensorData(Base):
    """Sensor data record representing one timestamp with multiple sensor readings.

    The hybrid storage model stores high-frequency/key sensors as explicit columns
    for efficient querying, while auxiliary sensors are stored in a JSON column
    for flexibility when schema requirements evolve.
    """

    __tablename__ = "sensor_data"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Timestamp index for time-series queries
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)

    # === Primary Device Measurements (explicit columns for query performance) ===
    # DM-PP*: Pump/Power related
    dm_pp01_r: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-PP01-R
    dm_pp01a_d: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-PP01A-D
    dm_pp01a_r: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-PP01A-R
    dm_pp01b_d: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-PP01B-D
    dm_pp01b_r: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-PP01B-R
    dm_pp02_d: Mapped[float | None] = mapped_column(Float, nullable=True)        # DM-PP02-D
    dm_pp02_r: Mapped[float | None] = mapped_column(Float, nullable=True)        # DM-PP02-R
    dm_pp04_d: Mapped[float | None] = mapped_column(Float, nullable=True)         # DM-PP04-D
    dm_pp04_ao: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-PP04-AO

    # DM-FT*: Flow transmitters
    dm_ft01: Mapped[float | None] = mapped_column(Float, nullable=True)         # DM-FT01
    dm_ft01z: Mapped[float | None] = mapped_column(Float, nullable=True)         # DM-FT01Z
    dm_ft02: Mapped[float | None] = mapped_column(Float, nullable=True)          # DM-FT02
    dm_ft02z: Mapped[float | None] = mapped_column(Float, nullable=True)          # DM-FT02Z
    dm_ft03: Mapped[float | None] = mapped_column(Float, nullable=True)          # DM-FT03
    dm_ft03z: Mapped[float | None] = mapped_column(Float, nullable=True)          # DM-FT03Z

    # DM-TIT*: Temperature indicators
    dm_tit01: Mapped[float | None] = mapped_column(Float, nullable=True)         # DM-TIT01
    dm_tit02: Mapped[float | None] = mapped_column(Float, nullable=True)          # DM-TIT02

    # DM-PIT*: Pressure indicators
    dm_pit01: Mapped[float | None] = mapped_column(Float, nullable=True)         # DM-PIT01
    dm_pit01_hh: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-PIT01-HH (high-high alarm)
    dm_pit02: Mapped[float | None] = mapped_column(Float, nullable=True)          # DM-PIT02

    # DM-LIT*: Level indicators
    dm_lit01: Mapped[float | None] = mapped_column(Float, nullable=True)          # DM-LIT01

    # DM-LCV/FCV*: Control valves
    dm_lcv01_d: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-LCV01-D
    dm_lcv01_z: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-LCV01-Z
    dm_fcv01_d: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-FCV01-D
    dm_fcv01_z: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-FCV01-Z
    dm_fcv02_d: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-FCV02-D
    dm_fcv02_z: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-FCV02-Z
    dm_fcv03_d: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-FCV03-D
    dm_fcv03_z: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-FCV03-Z

    # DM-PCV*: Pressure control valves
    dm_pcv01_d: Mapped[float | None] = mapped_column(Float, nullable=True)      # DM-PCV01-D
    dm_pcv01_z: Mapped[float | None] = mapped_column(Float, nullable=True)      # DM-PCV01-Z
    dm_pcv01_dev: Mapped[float | None] = mapped_column(Float, nullable=True)    # DM-PCV01-DEV
    dm_pcv02_d: Mapped[float | None] = mapped_column(Float, nullable=True)      # DM-PCV02-D
    dm_pcv02_z: Mapped[float | None] = mapped_column(Float, nullable=True)      # DM-PCV02-Z

    # DM-AIT*: Analytical indicators (DO: dissolved oxygen, PH: pH)
    dm_ait_do: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-AIT-DO
    dm_ait_ph: Mapped[float | None] = mapped_column(Float, nullable=True)        # DM-AIT-PH

    # DM-SOL*: Solenoid valves (binary, stored as float)
    dm_sol01_d: Mapped[float | None] = mapped_column(Float, nullable=True)      # DM-SOL01-D
    dm_sol02_d: Mapped[float | None] = mapped_column(Float, nullable=True)      # DM-SOL02-D
    dm_sol03_d: Mapped[float | None] = mapped_column(Float, nullable=True)      # DM-SOL03-D
    dm_sol04_d: Mapped[float | None] = mapped_column(Float, nullable=True)      # DM-SOL04-D

    # DM-LSH/LSL*: Level switches (binary)
    dm_lsh_03: Mapped[float | None] = mapped_column(Float, nullable=True)        # DM-LSH-03
    dm_lsh_04: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-LSH-04
    dm_lsl_04: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-LSL-04
    dm_lsh01: Mapped[float | None] = mapped_column(Float, nullable=True)         # DM-LSH01
    dm_lsh02: Mapped[float | None] = mapped_column(Float, nullable=True)         # DM-LSH02
    dm_lsl01: Mapped[float | None] = mapped_column(Float, nullable=True)        # DM-LSL01
    dm_lsl02: Mapped[float | None] = mapped_column(Float, nullable=True)        # DM-LSL02

    # DM-CIP*: Cleaning-in-place process values
    dm_cip_1st: Mapped[float | None] = mapped_column(Float, nullable=True)      # DM-CIP-1ST
    dm_cip_2nd: Mapped[float | None] = mapped_column(Float, nullable=True)      # DM-CIP-2ND
    dm_cip_start: Mapped[float | None] = mapped_column(Float, nullable=True)    # DM-CIP-START
    dm_cip_step1: Mapped[float | None] = mapped_column(Float, nullable=True)    # DM-CIP-STEP1
    dm_cip_step11: Mapped[float | None] = mapped_column(Float, nullable=True)   # DM-CIP-STEP11
    dm_ciph_1st: Mapped[float | None] = mapped_column(Float, nullable=True)     # DM-CIPH-1ST
    dm_ciph_2nd: Mapped[float | None] = mapped_column(Float, nullable=True)     # DM-CIPH-2ND
    dm_ciph_start: Mapped[float | None] = mapped_column(Float, nullable=True)   # DM-CIPH-START
    dm_ciph_step1: Mapped[float | None] = mapped_column(Float, nullable=True)   # DM-CIPH-STEP1
    dm_ciph_step11: Mapped[float | None] = mapped_column(Float, nullable=True)  # DM-CIPH-STEP11

    # DM-COOL*: Cooling system
    dm_cool_on: Mapped[float | None] = mapped_column(Float, nullable=True)      # DM-COOL-ON
    dm_cool_r: Mapped[float | None] = mapped_column(Float, nullable=True)        # DM-COOL-R

    # DM-HT*: Heating system
    dm_ht01_d: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-HT01-D

    # DM-TWIT*: Transmitter inputs
    dm_twit_03: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-TWIT-03
    dm_twit_04: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-TWIT-04
    dm_twit_05: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-TWIT-05
    dm_pwit_03: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-PWIT-03

    # DM-SS*: Soft starter
    dm_ss01_rm: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-SS01-RM

    # DM-ST/SP/EM*: Switch states
    dm_st_sp: Mapped[float | None] = mapped_column(Float, nullable=True)        # DM-ST-SP
    dm_sw01_st: Mapped[float | None] = mapped_column(Float, nullable=True)        # DM-SW01-ST
    dm_sw02_sp: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-SW02-SP
    dm_sw03_em: Mapped[float | None] = mapped_column(Float, nullable=True)       # DM-SW03-EM

    # Gate and setpoint
    gate_open: Mapped[float | None] = mapped_column(Float, nullable=True)       # GATEOPEN
    pp04_sp_out: Mapped[float | None] = mapped_column(Float, nullable=True)     # PP04-SP-OUT

    # DQ*: Distributed quality control valves
    dq03_lcv01_d: Mapped[float | None] = mapped_column(Float, nullable=True)    # DQ03-LCV01-D
    dq04_lcv01_dev: Mapped[float | None] = mapped_column(Float, nullable=True)   # DQ04-LCV01-DEV

    # === Extended Sensor Data (JSON for schema flexibility) ===
    # Stores all auxiliary sensors (NNNN.OUT tags) as key-value pairs
    # This allows adding/removing sensors without schema migration
    extra_sensors: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Auxiliary sensor readings as JSON"
    )

    def __repr__(self) -> str:
        return f"<SensorData(id={self.id}, timestamp={self.timestamp})>"
