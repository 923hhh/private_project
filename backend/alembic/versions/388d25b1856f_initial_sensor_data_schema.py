"""initial_sensor_data_schema

Revision ID: 388d25b1856f
Revises: 
Create Date: 2026-03-24 21:38:59.819844

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '388d25b1856f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'sensor_data',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('dm_pp01_r', sa.Float(), nullable=True),
        sa.Column('dm_pp01a_d', sa.Float(), nullable=True),
        sa.Column('dm_pp01a_r', sa.Float(), nullable=True),
        sa.Column('dm_pp01b_d', sa.Float(), nullable=True),
        sa.Column('dm_pp01b_r', sa.Float(), nullable=True),
        sa.Column('dm_pp02_d', sa.Float(), nullable=True),
        sa.Column('dm_pp02_r', sa.Float(), nullable=True),
        sa.Column('dm_pp04_d', sa.Float(), nullable=True),
        sa.Column('dm_pp04_ao', sa.Float(), nullable=True),
        sa.Column('dm_ft01', sa.Float(), nullable=True),
        sa.Column('dm_ft01z', sa.Float(), nullable=True),
        sa.Column('dm_ft02', sa.Float(), nullable=True),
        sa.Column('dm_ft02z', sa.Float(), nullable=True),
        sa.Column('dm_ft03', sa.Float(), nullable=True),
        sa.Column('dm_ft03z', sa.Float(), nullable=True),
        sa.Column('dm_tit01', sa.Float(), nullable=True),
        sa.Column('dm_tit02', sa.Float(), nullable=True),
        sa.Column('dm_pit01', sa.Float(), nullable=True),
        sa.Column('dm_pit01_hh', sa.Float(), nullable=True),
        sa.Column('dm_pit02', sa.Float(), nullable=True),
        sa.Column('dm_lit01', sa.Float(), nullable=True),
        sa.Column('dm_lcv01_d', sa.Float(), nullable=True),
        sa.Column('dm_lcv01_z', sa.Float(), nullable=True),
        sa.Column('dm_fcv01_d', sa.Float(), nullable=True),
        sa.Column('dm_fcv01_z', sa.Float(), nullable=True),
        sa.Column('dm_fcv02_d', sa.Float(), nullable=True),
        sa.Column('dm_fcv02_z', sa.Float(), nullable=True),
        sa.Column('dm_fcv03_d', sa.Float(), nullable=True),
        sa.Column('dm_fcv03_z', sa.Float(), nullable=True),
        sa.Column('dm_pcv01_d', sa.Float(), nullable=True),
        sa.Column('dm_pcv01_z', sa.Float(), nullable=True),
        sa.Column('dm_pcv01_dev', sa.Float(), nullable=True),
        sa.Column('dm_pcv02_d', sa.Float(), nullable=True),
        sa.Column('dm_pcv02_z', sa.Float(), nullable=True),
        sa.Column('dm_ait_do', sa.Float(), nullable=True),
        sa.Column('dm_ait_ph', sa.Float(), nullable=True),
        sa.Column('dm_sol01_d', sa.Float(), nullable=True),
        sa.Column('dm_sol02_d', sa.Float(), nullable=True),
        sa.Column('dm_sol03_d', sa.Float(), nullable=True),
        sa.Column('dm_sol04_d', sa.Float(), nullable=True),
        sa.Column('dm_lsh_03', sa.Float(), nullable=True),
        sa.Column('dm_lsh_04', sa.Float(), nullable=True),
        sa.Column('dm_lsl_04', sa.Float(), nullable=True),
        sa.Column('dm_lsh01', sa.Float(), nullable=True),
        sa.Column('dm_lsh02', sa.Float(), nullable=True),
        sa.Column('dm_lsl01', sa.Float(), nullable=True),
        sa.Column('dm_lsl02', sa.Float(), nullable=True),
        sa.Column('dm_cip_1st', sa.Float(), nullable=True),
        sa.Column('dm_cip_2nd', sa.Float(), nullable=True),
        sa.Column('dm_cip_start', sa.Float(), nullable=True),
        sa.Column('dm_cip_step1', sa.Float(), nullable=True),
        sa.Column('dm_cip_step11', sa.Float(), nullable=True),
        sa.Column('dm_ciph_1st', sa.Float(), nullable=True),
        sa.Column('dm_ciph_2nd', sa.Float(), nullable=True),
        sa.Column('dm_ciph_start', sa.Float(), nullable=True),
        sa.Column('dm_ciph_step1', sa.Float(), nullable=True),
        sa.Column('dm_ciph_step11', sa.Float(), nullable=True),
        sa.Column('dm_cool_on', sa.Float(), nullable=True),
        sa.Column('dm_cool_r', sa.Float(), nullable=True),
        sa.Column('dm_ht01_d', sa.Float(), nullable=True),
        sa.Column('dm_twit_03', sa.Float(), nullable=True),
        sa.Column('dm_twit_04', sa.Float(), nullable=True),
        sa.Column('dm_twit_05', sa.Float(), nullable=True),
        sa.Column('dm_pwit_03', sa.Float(), nullable=True),
        sa.Column('dm_ss01_rm', sa.Float(), nullable=True),
        sa.Column('dm_st_sp', sa.Float(), nullable=True),
        sa.Column('dm_sw01_st', sa.Float(), nullable=True),
        sa.Column('dm_sw02_sp', sa.Float(), nullable=True),
        sa.Column('dm_sw03_em', sa.Float(), nullable=True),
        sa.Column('gate_open', sa.Float(), nullable=True),
        sa.Column('pp04_sp_out', sa.Float(), nullable=True),
        sa.Column('dq03_lcv01_d', sa.Float(), nullable=True),
        sa.Column('dq04_lcv01_dev', sa.Float(), nullable=True),
        sa.Column('extra_sensors', sa.JSON(), nullable=True, comment='Auxiliary sensor readings as JSON'),
    )
    op.create_index('ix_sensor_data_timestamp', 'sensor_data', ['timestamp'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_sensor_data_timestamp', table_name='sensor_data')
    op.drop_table('sensor_data')
