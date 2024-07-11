from datetime import datetime
from pydantic import (
	BaseModel,
	Field,
	field_validator
)
from typing import Set

from .enums import DatasetOrigin


# For dual approach, where the pricing mechanism is not defined
class BaseUserParams(BaseModel):
	start_datetime: datetime = Field(
		description='Start datetime for the price calculation horizon (included in it) in ISO 8601 format.',
		examples=['2024-05-16T00:00:00Z']
	)
	end_datetime: datetime = Field(
		description='End datetime for the price calculation horizon (included in it) in ISO 8601 format.',
		examples=['2024-05-16T00:45:00Z']
	)
	dataset_origin: DatasetOrigin = Field(
		description='Dataset origin from which the meter IDs\' data is to be retrieved from. '
					'Two options are provided:\n - SEL (Smart Energy Lab)\n - CEVE (Cooperativa Elétrica Vale d\'Este',
		examples=['SEL']
	)
	meter_ids: Set[str] = Field(
		description='An array of strings that unequivocally identifies the meters to be included in the REC. <br />'
		            'All registered assets (i.e., meter ids) belonging totally or partially to the meters listed, '
		            'will be considered in the following computations.',
		examples=[('Meter#1', 'Meter#2')]
	)

	@field_validator('end_datetime')
	def is_end_after_start(cls, end_dt, values):
		start_dt = values.data['start_datetime']
		assert end_dt > start_dt, 'end_datetime <= start_datetime'
		return end_dt

	@field_validator('meter_ids')
	def more_than_one_meter(cls, ids):
		assert len(ids) > 1, 'please define at least 2 meters for the REC'
		return ids


class UserParams(BaseUserParams):
	sdr_compensation: float | None = Field(
		default=0.0,
		ge=0.0,
		le=1.0,
		description='Only considered when choosing "sdr" as the pricing mechanism. <br />'
		            'Defines a compensation between 0.0 and 1.0 allowing the user to set an incentive for internal '
		            'trades whenever the REC has a net surplus.'
	)
	mmr_divisor: int | None = Field(
		default=2,
		gt=0,
		description='Only considered when choosing "mmr" as the pricing mechanism. <br />'
		            'Defines the divisor considered on the MMR expression. Values greater than 2 will favor buyers '
		            'and values smaller than 2 will favor sellers.'
	)
