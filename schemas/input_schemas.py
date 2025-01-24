from datetime import (
	datetime,
	timezone
)
from pydantic import (
	BaseModel,
	Field,
	field_validator
)
from typing import (
	Optional,
	Set
)

from .enums import DatasetOrigin


########################################################################################################################
# COMMON VALiDATORS
########################################################################################################################
def meter_id_not_found(mi, values):
	assert all(struct.meter_id in values.data.get('meter_ids') for struct in mi), \
		'one or more meter_id not found in field meter_ids'
	return mi


def shared_meter_id_not_found(smi, values):
	assert all(struct.meter_id in values.data.get('shared_meter_ids') for struct in smi), \
		'one or more meter_id not found in field shared_meter_ids'
	return smi


########################################################################################################################
# LOW LEVEL STRUCTURES
########################################################################################################################
class MeterID(BaseModel):
	meter_id: str = Field(
		description='The string that unequivocally identifies the meter.',
		examples=['Meter#X']
	)


class InstalledPVCapacity(MeterID):
	installed_pv_capacity: float = Field(
		ge=0.0,
		description='Installed PV capacity that will overrule the original PV capacity of the meter, in kVA.',
		examples=[5.0]
	)


class Storage(MeterID):
	e_bn: float = Field(
		ge=0.0,
		description='Storage\'s energy capacity, in kWh.',
		examples=[5.0]
	)
	p_max: float = Field(
		ge=0.0,
		description='Storage\'s maximum power rate (for charge and discharge), in kW.',
		examples=[5.0]
	)
	soc_min: float = Field(
		ge=0.0,
		le=100.0,
		description='Minimum state-of-charge to consider for the storage asset, in %.',
		examples=[0.0]
	)
	soc_max: float = Field(
		ge=0.0,
		le=100.0,
		description='Maximum state-of-charge to consider for the storage asset, in %.',
		examples=[100.0]
	)
	eff_bc: float = Field(
		ge=0.0,
		le=100.0,
		description='Charging efficiency of the storage asset, in %.',
		examples=[100.0]
	)
	eff_bd: float = Field(
		ge=0.0,
		le=100.0,
		description='Discharging efficiency of the storage asset, in %.',
		examples=[100.0]
	)
	deg_cost: float = Field(
		ge=0.0,
		description='Degradation cost of the storage asset, in %.',
		examples=[0.01]
	)

	@field_validator('soc_max')
	def is_soc_max_greater_than_soc_min(cls, soc_max, values):
		soc_min = values.data['soc_min']
		assert soc_max >= soc_min, 'soc_max < soc_min'
		return soc_max


class ContractedPower(MeterID):
	contracted_power: float = Field(
		ge=0.0,
		description='Contracted power at the meter, in kVA.',
		examples=[6.9]
	)


########################################################################################################################
# HIGH LEVEL STRUCTURES
########################################################################################################################
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
					'Two options are provided:\n - SEL (Smart Energy Lab)\n - INDATA',
		examples=['SEL']
	)
	meter_ids: Set[str] = Field(
		description='An array of strings that unequivocally identifies the meters to be included in the REC. <br />'
		            'All registered assets (i.e., meter ids) belonging totally or partially to the meters listed, '
		            'will be considered in the following computations.',
		examples=[('Meter#1', 'Meter#2')]
	)
	meter_installed_pv_capacities: Optional[list[InstalledPVCapacity]] = Field(
		default=[],
		description='Defines, for the list of meters provided, '
					'what are the installed PV capacities to be considered.  <br />'
					'If this field or any specific structure regarding a meter ID defined in the '
					'"meter_ids" field is not provided, the original PV capacities of the missing meters will be '
					'considered.',
	)
	shared_meter_ids: Optional[Set[str]] = Field(
		default=[],
		description='An array of strings that unequivocally identifies the new shared meters to be included '
					'in the REC.',
		examples=[('Meter#3', 'Meter#4')]
	)
	shared_meter_installed_pv_capacities: Optional[list[InstalledPVCapacity]] = Field(
		default=[],
		description='Defines, for the list of shared meters provided, '
					'what are the installed PV capacities to be considered.  <br />'
					'If this field or any specific structure regarding a shared meter ID defined in the '
					'"shared_meter_ids" field is not provided, no PV capacity will be considered for the '
					'missing meters.',
	)

	@field_validator('start_datetime')
	def parse_start_datetime(cls, start_dt):
		return start_dt.astimezone(timezone.utc)

	@field_validator('end_datetime')
	def parse_start_endtime(cls, end_dt):
		return end_dt.astimezone(timezone.utc)

	@field_validator('end_datetime')
	def is_end_after_start(cls, end_dt, values):
		start_dt = values.data['start_datetime']
		assert end_dt > start_dt, 'end_datetime <= start_datetime'
		return end_dt

	@field_validator('meter_ids')
	def more_than_one_meter(cls, ids):
		assert len(ids) > 1, 'please define at least 2 meters for the REC'
		return ids

	@field_validator('meter_installed_pv_capacities')
	def meter_id_in_pv_installed_capacities_not_found(cls, mipv, values):
		return meter_id_not_found(mipv, values)

	@field_validator('shared_meter_installed_pv_capacities')
	def shared_meter_id_in_pv_installed_capacities_not_found(cls, mipv, values):
		return shared_meter_id_not_found(mipv, values)


class PricingUserParams(BaseModel):
	sdr_compensation: Optional[float] = Field(
		default=0.0,
		ge=0.0,
		le=1.0,
		description='Only considered when choosing "sdr" as the pricing mechanism. <br />'
					'Defines a compensation between 0.0 and 1.0 allowing the user to set an incentive for internal '
					'trades whenever the REC has a net surplus.'
	)
	mmr_divisor: Optional[int] = Field(
		default=2,
		gt=0,
		description='Only considered when choosing "mmr" as the pricing mechanism. <br />'
					'Defines the divisor considered on the MMR expression. Values greater than 2 will favor buyers '
					'and values smaller than 2 will favor sellers.'
	)


class MILPBaseUserParams(BaseUserParams):
	meter_storage: Optional[list[Storage]] = Field(
		default=[],
		description='Defines, for the list of meters provided, '
					'what are the installed PV capacities to be considered.  <br />'
					'If this field or any specific structure regarding a meter ID defined in the '
					'"meter_ids" field is not provided, no storage capacities for the missing meters will be '
					'considered.',
	)
	shared_meter_storage: Optional[list[Storage]] = Field(
		default=[],
		description='Defines, for the list of shared meters provided, '
					'what are the installed PV capacities to be considered.  <br />'
					'If this field or any specific structure regarding a meter ID defined in the '
					'"shared_meter_ids" field is not provided, no storage capacities for the missing meters will be '
					'considered.',
	)
	meter_contracted_power: Optional[list[ContractedPower]] = Field(
		default=[],
		description='Defines, for the list of meters provided, '
					'what are the installed PV capacities to be considered.  <br />'
					'If this field or any specific structure regarding a meter ID defined in the '
					'"meter_ids" field is not provided, a default value equal to the maximum possible '
					'contracted power in BTN (low voltage) will be considered: 41.4 kVA.',
	)
	shared_meter_contracted_power: Optional[list[ContractedPower]] = Field(
		default=[],
		description='Defines, for the list of shared meters provided, '
					'what are the installed PV capacities to be considered.  <br />'
					'If this field or any specific structure regarding a meter ID defined in the '
					'"shared_meter_ids" field is not provided, a default value equal to the maximum possible '
					'contracted power in BTN (low voltage) will be considered: 41.4 kVA.',
	)

	@field_validator('meter_storage')
	def meter_id_in_storage_not_found(cls, mis, values):
		return meter_id_not_found(mis, values)

	@field_validator('shared_meter_storage')
	def shared_meter_id_in_storage_not_found(cls, smis, values):
		return shared_meter_id_not_found(smis, values)

	@field_validator('meter_contracted_power')
	def meter_id_in_contracted_power_not_found(cls, micp, values):
		return meter_id_not_found(micp, values)

	@field_validator('shared_meter_contracted_power')
	def shared_meter_id_in_contracted_power_not_found(cls, smicp, values):
		return shared_meter_id_not_found(smicp, values)


########################################################################################################################
# FUNCTION INPUT SCHEMAS
########################################################################################################################
class VanillaUserParams(BaseUserParams, PricingUserParams):
	pass


class DualUserParams(MILPBaseUserParams):
	pass


class LoopUserParams(MILPBaseUserParams, PricingUserParams):
	pass
