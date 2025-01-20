from enum import Enum


class PricingMechanism(str, Enum):
	crossing_value = 'crossing_value'
	mmr = 'mmr'
	sdr = 'sdr'


class LemOrganization(str, Enum):
	pool = 'pool'
	bilateral = 'bilateral'


class DatasetOrigin(str, Enum):
	indata = 'INDATA'
	sel = 'SEL'


class OfferType(str, Enum):
	buy = 'buy'
	sell = 'sell'


class MILPStatus(str, Enum):
	optimal = 'Optimal',
	unbounded = 'Unbounded',
	infeasible = 'Infeasible'
