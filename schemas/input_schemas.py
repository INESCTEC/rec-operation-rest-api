from datetime import datetime
from .enums import LemOrganization
from pydantic import (
	BaseModel,
	Field,
	field_validator
)
from typing import (
	Annotated,
	Set
)


class UserParams(BaseModel):
	start_datetime: datetime = Field(
		description='Start datetime for the price calculation horizon (included in it) in ISO 8601 format.'
	)
	end_datetime: datetime = Field(
		description='End datetime for the price calculation horizon (included in it) in ISO 8601 format.'
	)
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
	member_ids: Set[str] = Field(
		description='An array of strings that unequivocally identifies the members to be included in the REC. <br />'
		            'All registered assets (i.e., meter ids) belonging totally or partially to the members listed, '
		            'will be considered in the following computations.',
		examples=[('Member#1', 'Member#2')]
	)

	@field_validator('end_datetime')
	def is_end_after_start(cls, end_dt, values):
		start_dt = values.data['start_datetime']
		assert end_dt > start_dt, 'end_datetime <= start_datetime'
		return end_dt


class MILPUserParams(UserParams):
	lem_organization: LemOrganization | None = Field(
		default='pool',
		description='Type of local energy market organization. Defines how transactions between members take place, '
		            'either in a pool fashion (i.e., only total energy sold and bought is defined per meter ID) or '
		            'through the establishment of bilateral agreements.'
	)
	contracted_power_penalty: float | None = Field(
		default=1.0E3,
		ge=0.0,
		description='A fictitious penalty for overlapping the contracted power at any given instant in the '
		            'meters. <br />'
		            'The default value is big enough to consider that overlapping is not possible.'
	)
	enforce_positive_ac: bool | None = Field(
		default=True,
		description='Under Portuguese legislation, it is required that the allocation coefficients that define energy '
		            'transactions in a local energy market are strictly positive. By setting this parameter to True, '
		            'the user explicits that such restriction must be considered in the MILP to be solved.'
	)
	apply_storage_deg_cost: bool | None = Field(
		default=False,
		description='If the user desires, a price can be applied for BESS degradation in the MILP solved. '
		            'It will be applicable to all energy discharged from the assets. <br />'
		            'The price is specific for each BESS asset and will only be applied if it is available in the '
		            'respective database (possibly defined during the asset\'s registration).'
	)
