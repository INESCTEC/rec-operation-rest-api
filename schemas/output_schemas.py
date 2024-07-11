from datetime import datetime as dt
from pydantic import (
	BaseModel,
	Field
)
from .enums import (
	MILPStatus,
	OfferType
)


# IMMEDIATE RESPONSE ###################################################################################################
class AcceptedResponse(BaseModel):
	message: str = Field(
		examples=['Processing has started. Use the order ID for status updates.']
	)
	order_id: str = Field(
		description='Order identifier for the request. <br />'
		            'Request results via REST API can only be retrieved by specifying this identifier.',
		examples=['iaMiULXA9BktPUu2b_PwTtycCSNe0_wYpPt9muwlEtgL49GDg-kggSktAjtu']
	)


# NON-OK RESPONSES #####################################################################################################
class OrderNotFound(BaseModel):
	message: str = Field(
		examples=['Order not found.']
	)
	order_id: str = Field(
		max_length=45,
		min_length=45,
		description='Order identifier for the request.',
		examples=['iaMiULXA9BktPUu2b_PwTtycCSNe0_wYpPt9muwlEtgL49GDg-kggSktAjtu']
	)


class OrderNotProcessed(BaseModel):
	message: str = Field(
		examples=['Order found, but not yet processed. Please try again later.']
	)
	order_id: str = Field(
		max_length=45,
		min_length=45,
		description='Order identifier for the request.',
		examples=['iaMiULXA9BktPUu2b_PwTtycCSNe0_wYpPt9muwlEtgL49GDg-kggSktAjtu']
	)


class MeterIDNotFound(BaseModel):
	message: str = Field(
		examples=['One or more meter IDs not found on registry system.']
	)
	missing_ids: list[str] = Field(
		description='List with meter IDs missing from the registry system.',
		examples=[['Meter#1', 'Meter#2']]
	)
	order_id: str = Field(
		max_length=45,
		min_length=45,
		description='Order identifier for the request.',
		examples=['iaMiULXA9BktPUu2b_PwTtycCSNe0_wYpPt9muwlEtgL49GDg-kggSktAjtu']
	)


class TimeseriesDataNotFound(BaseModel):
	message: str = Field(
		examples=['One or more data point for one or more meter IDs not found on registry system.']
	)
	missing_data_points: dict[str, list[str]] = Field(
		description='Lists of missing data points\' datetime per meter ID.',
		examples=[{'Meter#1': ['2024-05-16T00:00:00Z', '2024-05-16T00:15:00Z']}]
	)
	order_id: str = Field(
		max_length=45,
		min_length=45,
		description='Order identifier for the request.',
		examples=['iaMiULXA9BktPUu2b_PwTtycCSNe0_wYpPt9muwlEtgL49GDg-kggSktAjtu']
	)


# VANILLA RESPONSE #####################################################################################################
class Offer(BaseModel):
	datetime: dt = Field(
		description='Datetime in ISO 8601 format.',
		examples=['2024-05-16T00:45:00Z']
	)
	meter_id: str = Field(
		description='The string that unequivocally identifies the meter of the REC that made the offer.',
		examples=['Meter#1']
	)
	amount: float = Field(
		ge=0.0,
		description='Amount offered in the session, in kWh.'
	)
	value: float = Field(
		ge=0.0,
		description='Price offered in the session, in €/kwh.'
	)
	type: OfferType = Field(
		description='Indicates if it is a buying or selling offer.'
	)


class LemPrice(BaseModel):
	datetime: dt = Field(
		description='Datetime in ISO 8601 format.',
		examples=['2024-05-16T00:45:00Z']
	)
	value: float = Field(
		ge=0.0,
		description='Local energy market price computed, in €/kWh.'
	)


class VanillaOutputs(BaseModel):
	order_id: str = Field(
		max_length=60,
		min_length=60,
		description='Order identifier for the request.',
		examples=['iaMiULXA9BktPUu2b_PwTtycCSNe0_wYpPt9muwlEtgL49GDg-kggSktAjtu']
	)
	lem_prices: list[LemPrice] = Field(
		description='List with the local energy market prices computed for the requested horizon.'
	)
	offers: list[Offer] = Field(
		description='A description of all the offers considered in the local energy market session that resulted in '
		            'the calculated price.'
	)


# MILP RESPONSE ########################################################################################################
class InputsPerMeterAndDatetime(BaseModel):
	meter_id: str = Field(
		description='A string that unequivocally identifies a meter of the REC.',
		examples=['Meter#1']
	)
	datetime: dt = Field(
		description='Datetime in ISO 8601 format.',
		examples=['2024-05-16T00:45:00Z']
	)
	energy_generated: float = Field(
		description='PV panels’ generation considered by the algorithm, in kWh.',
		examples=[5.0]
	)
	energy_consumed: float = Field(
		description='Meter\'s consumption considered by the algorithm, in kWh.',
		examples=[5.0]
	)
	buy_tariff: float = Field(
		description='Purchase rate agreed with the retailer that was considered by the algorithm, in €/kWh.',
		examples=[5.0]
	)
	sell_tariff: float = Field(
		description='Selling rate agreed with the retailer that was considered by the algorithm, in €/kWh.',
		examples=[5.0]
	)


class OutputsPerMeterAndDatetime(BaseModel):
	meter_id: str = Field(
		description='A string that unequivocally identifies a meter of the REC.',
		examples=['Meter#1']
	)
	datetime: dt = Field(
		description='Datetime in ISO 8601 format.',
		examples=['2024-05-16T00:45:00Z']
	)
	energy_surplus: float = Field(
		description='Energy surplus that was sold to the retailer, in kWh.',
		examples=[5.0]
	)
	energy_supplied: float = Field(
		description='Energy supplied that was bought from the retailer, in kWh.',
		examples=[5.0]
	)
	net_load: float = Field(
		description='Expected net load registered in the meter, in kWh.',
		examples=[5.0]
	)
	bess_energy_charged: float = Field(
		description='Energy charged in the meter\'s BESS, in kWh. <br />'
					'Sent as 0.0 if the meter does not have storage.',
		examples=[5.0]
	)
	bess_energy_discharged: float = Field(
		description='Energy discharged in the meter\'s BESS, in kWh. <br />'
					'Sent as 0.0 if the meter does not have storage.',
		examples=[5.0]
	)
	bess_energy_content: float = Field(
		description='Energy content of the meter\'s BESS, at the end of the time interval, in kWh. <br />'
					'Sent as 0.0 if the meter does not have storage.',
		examples=[5.0]
	)


class PoolLEMTransactions(BaseModel):
	meter_id: str = Field(
		description='A string that unequivocally identifies a meter of the REC.',
		examples=['Meter#1']
	)
	datetime: dt = Field(
		description='Datetime in ISO 8601 format.',
		examples=['2024-05-16T00:45:00Z']
	)
	energy_purchased_lem: float = Field(
		description='Energy that was purchased in the local energy market (LEM), in kWh.',
		examples=[5.0]
	)
	energy_sold_lem: float = Field(
		description='Energy that was sold in the local energy market (LEM), in kWh.',
		examples=[5.0]
	)
	sold_position: float = Field(
		description='Sold position of the meter ID, for the datetime, '
					'calculated as the energy sold minus the energy bought in the LEM, in kWh.',
		examples=[0.0]
	)


class BilateralLEMTransactions(BaseModel):
	provider_meter_id: str = Field(
		description='A string that unequivocally identifies the providing meter of the REC.',
		examples=['Meter#1']
	)
	receiver_meter_id: str = Field(
		description='A string that unequivocally identifies the receiving meter of the REC.',
		examples=['Meter#2']
	)
	datetime: dt = Field(
		description='Datetime in ISO 8601 format.',
		examples=['2024-05-16T00:45:00Z']
	)
	energy: float = Field(
		description='Energy transacted in the local energy market (LEM), in kWh.',
		examples=[5.0]
	)


class IndividualCosts(BaseModel):
	meter_id: str = Field(
		description='A string that unequivocally identifies a meter of the REC.',
		examples=['Meter#1']
	)
	individual_cost: float = Field(
		description='The operation cost for the optimization horizon calculated for the meter ID, '
					'without considering the cost for degradation of the BESS, in €.',
		examples=[5.0]
	)


class PoolSelfConsumptionTariffsPerDatetime(BaseModel):
	datetime: dt = Field(
		description='Datetime in ISO 8601 format.',
		examples=['2024-05-16T00:45:00Z']
	)
	self_consumption_tariff: float = Field(
		description='Tariff applicable to self-consumed energy from the public grid, '
					'published by the national regulatory entity for energy services, in €/kWh.',
		examples=[5.0]
	)


class BilateralSelfConsumptionTariffsPerDatetime(BaseModel):
	datetime: dt = Field(
		description='Datetime in ISO 8601 format.',
		examples=['2024-05-16T00:45:00Z']
	)
	provider_meter_id: str = Field(
		description='A string that unequivocally identifies the providing meter of the REC.',
		examples=['Meter#1']
	)
	receiver_meter_id: str = Field(
		description='A string that unequivocally identifies the receiving meter of the REC.',
		examples=['Meter#2']
	)
	self_consumption_tariff: float = Field(
		description='Tariff applicable to self-consumed energy from the public grid, '
					'published by the national regulatory entity for energy services, in €/kWh. '
					'This tariff is payable by the receiving_member_id when purchasing energy '
					'in the LEM from the provider_member_id.',
		examples=[5.0]
	)


class PoolMILPOutputs(BaseModel):
	order_id: str = Field(
		max_length=60,
		min_length=60,
		description='Order identifier for the request.',
		examples=['iaMiULXA9BktPUu2b_PwTtycCSNe0_wYpPt9muwlEtgL49GDg-kggSktAjtu']
	)
	objective_value: float = Field(
		description='Objective value found for the MILP solution.',
		examples=[5.0]
	)
	milp_status: MILPStatus = Field(
		description='Indicates if the MILP was optimally solved (by returning "Optimal") or if an issue was raised '
					'and a successful solution was not achieved (by returning "Infeasible" or "Unbounded").'
	)
	total_rec_cost: float = Field(
		description='Total operation cost for the whole community, in €.',
		examples=[5.0]
	)
	individual_costs: list[IndividualCosts] = Field(
		description='Individual operation cost per meter ID, in €.'
	)
	meter_inputs: list[InputsPerMeterAndDatetime] = Field(
		description='All time-varying inputs that were fed into the MILP, per meter ID.'
	)
	meter_outputs: list[OutputsPerMeterAndDatetime] = Field(
		description='Time-varying outputs calculated in the MILP, per meter ID.'
	)
	lem_transactions: list[PoolLEMTransactions] = Field(
		description='List with total energies bought and sold in the LEM, per meter ID and per datetime.'
	)
	lem_prices: list[LemPrice] = Field(
		description='List with the local energy market prices computed for the requested horizon.'
	)
	self_consumption_tariffs: list[PoolSelfConsumptionTariffsPerDatetime] = Field(
		description='List with the self-consumption tariffs considered by the MILP.'
	)


class BilateralMILPOutputs(BaseModel):
	order_id: str = Field(
		max_length=60,
		min_length=60,
		description='Order identifier for the request.',
		examples=['iaMiULXA9BktPUu2b_PwTtycCSNe0_wYpPt9muwlEtgL49GDg-kggSktAjtu']
	)
	objective_value: float = Field(
		description='Objective value found for the MILP solution.',
		examples=[5.0]
	)
	milp_status: MILPStatus = Field(
		description='Indicates if the MILP was optimally solved (by returning "Optimal") or if an issue was raised '
					'and a successful solution was not achieved (by returning "Infeasible" or "Unbounded").'
	)
	total_rec_cost: float = Field(
		description='Total operation cost for the whole community, in €.',
		examples=[5.0]
	)
	individual_costs: list[IndividualCosts] = Field(
		description='Individual operation cost per meter ID, in €.'
	)
	meter_inputs: list[InputsPerMeterAndDatetime] = Field(
		description='All time-varying inputs that were fed into the MILP, per meter ID.'
	)
	meter_outputs: list[OutputsPerMeterAndDatetime] = Field(
		description='Time-varying outputs calculated in the MILP, per meter ID.'
	)
	lem_transactions: list[BilateralLEMTransactions] = Field(
		description='List with energies bought and sold in the LEM, per pair of meter IDs and per datetime.'
	)
	lem_prices: list[LemPrice] = Field(
		description='List with the local energy market prices computed for the requested horizon.'
	)
	self_consumption_tariffs: list[BilateralSelfConsumptionTariffsPerDatetime] = Field(
		description='List with the self-consumption tariffs considered by the MILP, per pair of meter IDs.'
	)
