# File: app/schemas/sensor_data.py
"""Pydantic V2 schemas for sensor data validation.

Auto-generated from app/models/sensor_data.py
Ensures type consistency between ORM models and API layer.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SensorDataBase(BaseModel):
    """Base schema with all sensor fields (no id/timestamp for creation)."""

    # DM-PP*: Pump/Power related
    dm_pp01_r: float | None = None
    dm_pp01a_d: float | None = None
    dm_pp01a_r: float | None = None
    dm_pp01b_d: float | None = None
    dm_pp01b_r: float | None = None
    dm_pp02_d: float | None = None
    dm_pp02_r: float | None = None
    dm_pp04_d: float | None = None
    dm_pp04_ao: float | None = None

    # DM-FT*: Flow transmitters
    dm_ft01: float | None = None
    dm_ft01z: float | None = None
    dm_ft02: float | None = None
    dm_ft02z: float | None = None
    dm_ft03: float | None = None
    dm_ft03z: float | None = None

    # DM-TIT*: Temperature indicators
    dm_tit01: float | None = None
    dm_tit02: float | None = None

    # DM-PIT*: Pressure indicators
    dm_pit01: float | None = None
    dm_pit01_hh: float | None = None
    dm_pit02: float | None = None

    # DM-LIT*: Level indicators
    dm_lit01: float | None = None

    # DM-LCV/FCV*: Control valves
    dm_lcv01_d: float | None = None
    dm_lcv01_z: float | None = None
    dm_fcv01_d: float | None = None
    dm_fcv01_z: float | None = None
    dm_fcv02_d: float | None = None
    dm_fcv02_z: float | None = None
    dm_fcv03_d: float | None = None
    dm_fcv03_z: float | None = None

    # DM-PCV*: Pressure control valves
    dm_pcv01_d: float | None = None
    dm_pcv01_z: float | None = None
    dm_pcv01_dev: float | None = None
    dm_pcv02_d: float | None = None
    dm_pcv02_z: float | None = None

    # DM-AIT*: Analytical indicators
    dm_ait_do: float | None = None
    dm_ait_ph: float | None = None

    # DM-SOL*: Solenoid valves
    dm_sol01_d: float | None = None
    dm_sol02_d: float | None = None
    dm_sol03_d: float | None = None
    dm_sol04_d: float | None = None

    # DM-LSH/LSL*: Level switches
    dm_lsh_03: float | None = None
    dm_lsh_04: float | None = None
    dm_lsl_04: float | None = None
    dm_lsh01: float | None = None
    dm_lsh02: float | None = None
    dm_lsl01: float | None = None
    dm_lsl02: float | None = None

    # DM-CIP*: Cleaning-in-place
    dm_cip_1st: float | None = None
    dm_cip_2nd: float | None = None
    dm_cip_start: float | None = None
    dm_cip_step1: float | None = None
    dm_cip_step11: float | None = None
    dm_ciph_1st: float | None = None
    dm_ciph_2nd: float | None = None
    dm_ciph_start: float | None = None
    dm_ciph_step1: float | None = None
    dm_ciph_step11: float | None = None

    # DM-COOL*: Cooling system
    dm_cool_on: float | None = None
    dm_cool_r: float | None = None

    # DM-HT*: Heating system
    dm_ht01_d: float | None = None

    # DM-TWIT*: Transmitter inputs
    dm_twit_03: float | None = None
    dm_twit_04: float | None = None
    dm_twit_05: float | None = None
    dm_pwit_03: float | None = None

    # DM-SS*: Soft starter
    dm_ss01_rm: float | None = None

    # DM-ST/SP/EM*: Switch states
    dm_st_sp: float | None = None
    dm_sw01_st: float | None = None
    dm_sw02_sp: float | None = None
    dm_sw03_em: float | None = None

    # Gate and setpoint
    gate_open: float | None = None
    pp04_sp_out: float | None = None

    # DQ*: Distributed quality control
    dq03_lcv01_d: float | None = None
    dq04_lcv01_dev: float | None = None

    # Extended sensors (JSON)
    extra_sensors: dict[str, Any] | None = Field(
        default=None,
        description="Auxiliary sensor readings as JSON"
    )


class SensorDataCreate(SensorDataBase):
    """Schema for creating a new sensor data record."""

    timestamp: datetime = Field(..., description="Measurement timestamp")


class SensorDataUpdate(BaseModel):
    """Schema for updating an existing sensor data record."""

    timestamp: datetime | None = None
    dm_pp01_r: float | None = None
    dm_pp01a_d: float | None = None
    dm_pp01a_r: float | None = None
    dm_pp01b_d: float | None = None
    dm_pp01b_r: float | None = None
    dm_pp02_d: float | None = None
    dm_pp02_r: float | None = None
    dm_pp04_d: float | None = None
    dm_pp04_ao: float | None = None
    dm_ft01: float | None = None
    dm_ft01z: float | None = None
    dm_ft02: float | None = None
    dm_ft02z: float | None = None
    dm_ft03: float | None = None
    dm_ft03z: float | None = None
    dm_tit01: float | None = None
    dm_tit02: float | None = None
    dm_pit01: float | None = None
    dm_pit01_hh: float | None = None
    dm_pit02: float | None = None
    dm_lit01: float | None = None
    dm_lcv01_d: float | None = None
    dm_lcv01_z: float | None = None
    dm_fcv01_d: float | None = None
    dm_fcv01_z: float | None = None
    dm_fcv02_d: float | None = None
    dm_fcv02_z: float | None = None
    dm_fcv03_d: float | None = None
    dm_fcv03_z: float | None = None
    dm_pcv01_d: float | None = None
    dm_pcv01_z: float | None = None
    dm_pcv01_dev: float | None = None
    dm_pcv02_d: float | None = None
    dm_pcv02_z: float | None = None
    dm_ait_do: float | None = None
    dm_ait_ph: float | None = None
    dm_sol01_d: float | None = None
    dm_sol02_d: float | None = None
    dm_sol03_d: float | None = None
    dm_sol04_d: float | None = None
    dm_lsh_03: float | None = None
    dm_lsh_04: float | None = None
    dm_lsl_04: float | None = None
    dm_lsh01: float | None = None
    dm_lsh02: float | None = None
    dm_lsl01: float | None = None
    dm_lsl02: float | None = None
    dm_cip_1st: float | None = None
    dm_cip_2nd: float | None = None
    dm_cip_start: float | None = None
    dm_cip_step1: float | None = None
    dm_cip_step11: float | None = None
    dm_ciph_1st: float | None = None
    dm_ciph_2nd: float | None = None
    dm_ciph_start: float | None = None
    dm_ciph_step1: float | None = None
    dm_ciph_step11: float | None = None
    dm_cool_on: float | None = None
    dm_cool_r: float | None = None
    dm_ht01_d: float | None = None
    dm_twit_03: float | None = None
    dm_twit_04: float | None = None
    dm_twit_05: float | None = None
    dm_pwit_03: float | None = None
    dm_ss01_rm: float | None = None
    dm_st_sp: float | None = None
    dm_sw01_st: float | None = None
    dm_sw02_sp: float | None = None
    dm_sw03_em: float | None = None
    gate_open: float | None = None
    pp04_sp_out: float | None = None
    dq03_lcv01_d: float | None = None
    dq04_lcv01_dev: float | None = None
    extra_sensors: dict[str, Any] | None = None


class SensorDataResponse(SensorDataBase):
    """Schema for sensor data API responses (includes id)."""

    id: int
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
