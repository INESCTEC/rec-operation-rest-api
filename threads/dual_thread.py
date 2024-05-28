import sqlite3

from loguru import logger

from helpers.dataspace_interactions import fetch_dataspace
from helpers.main_helpers import milp_inputs
from rec_op_lem_prices.optimization_functions import run_pre_single_stage_collective_pool_milp
from schemas.input_schemas import BaseUserParams


def run_dual_thread(user_params: BaseUserParams,
					id_order: str,
					conn: sqlite3.Connection,
					curs: sqlite3.Cursor):
	# get the necessary meters' data from the dataspace
	logger.info('[THREAD] Fetching data from dataspace.')
	data_df, list_of_datetimes, missing_ids, missing_dts = fetch_dataspace(user_params)
	meter_ids = set(data_df['meter_id'])

	# if any missing meter ids or missing datetimes in the data for those meter ids was found,
	# update the database with an error and an indication of which data is missing
	if missing_ids:
		logger.warning('[THREAD] Missing meter IDs in dataspace.')
		message = f'One or more meter IDs not found on registry system: {missing_ids}'
		curs.execute('''
			UPDATE Orders
			SET processed = ?, error = ?, message = ?
			WHERE order_id = ?
		''', (True, '412', message, id_order))
		conn.commit()

	elif any(missing_dts.values()):
		logger.warning('[THREAD] Missing data points in dataspace.')
		missing_pairs = {k: v for k, v in missing_dts.items() if v}
		message = f'One or more data point for one or more meter IDs not found on registry system: {missing_pairs}'
		curs.execute('''
			UPDATE Orders
			SET processed = ?, error = ?, message = ?
			WHERE order_id = ?
		''', (True, '422', message, id_order))
		conn.commit()

	# otherwise, proceed normally
	else:
		# prepare the inputs for the MILP
		logger.info('[THREAD] Building inputs.')
		inputs = milp_inputs(data_df, 'pool')

		# run optimization
		logger.info('[THREAD] Running MILP.')
		results = run_pre_single_stage_collective_pool_milp(inputs)

		# update the database with the new order ID
		logger.info('[THREAD] Updating database with results.')
		curs.execute('''
			UPDATE Orders
			SET processed = ?
			WHERE order_id = ?
		''', (True, id_order))

		curs.execute('''
			INSERT INTO General_MILP_Outputs (order_id, objective_value, milp_status, total_rec_cost)
			VALUES (?, ?, ?, ?)
		''', (
			id_order,
			round(results['obj_value'], 2),
			results['milp_status'],
			round(sum(results['c_ind2pool_without_deg_and_p_extra'].values()), 2)
		))

		for meter_id in meter_ids:
			curs.execute('''
				INSERT INTO Individual_Costs (order_id, meter_id, individual_cost)
				VALUES (?, ?, ?)
			''', (
				id_order,
				meter_id,
				round(results['c_ind2pool_without_deg_and_p_extra'][meter_id], 2)
			))

		for idx, dt in enumerate(list_of_datetimes):
			curs.execute('''
				INSERT INTO Lem_Prices (order_id, datetime, value)
				VALUES (?, ?, ?)
			''', (
				id_order,
				dt,
				results['dual_prices'][idx]
			))

			curs.execute('''
				INSERT INTO Pool_Self_Consumption_Tariffs (order_id, datetime, self_consumption_tariff)
				VALUES (?, ?, ?)
			''', (
				id_order,
				dt,
				inputs['l_grid'][idx]
			))

			for meter_id in meter_ids:
				curs.execute('''
					INSERT INTO Meter_Inputs (order_id, meter_id, datetime, energy_generated, 
						energy_consumed, buy_tariff, sell_tariff)
					VALUES (?, ?, ?, ?, ?, ?, ?)
				''', (
					id_order,
					meter_id,
					dt,
					inputs['meters'][meter_id]['e_g'][idx],
					inputs['meters'][meter_id]['e_c'][idx],
					inputs['meters'][meter_id]['l_buy'][idx],
					inputs['meters'][meter_id]['l_sell'][idx],
				))

				curs.execute('''
					INSERT INTO Meter_Outputs (order_id, meter_id, datetime, energy_surplus, 
						energy_supplied, net_load, 
						bess_energy_charged, bess_energy_discharged, bess_energy_content)
					VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
				''', (
					id_order,
					meter_id,
					dt,
					results['e_sur_retail'][meter_id][idx],
					results['e_sup_retail'][meter_id][idx],
					results['e_cmet'][meter_id][idx],
					0 if not bool(results['e_bc'][meter_id]) else results['e_bc'][meter_id][f'storage_{meter_id}'][idx],
					0 if not bool(results['e_bd'][meter_id]) else results['e_bc'][meter_id][f'storage_{meter_id}'][idx],
					0 if not bool(results['e_bat'][meter_id]) else results['e_bc'][meter_id][f'storage_{meter_id}'][idx],
				))

				curs.execute('''
					INSERT INTO Pool_LEM_Transactions (order_id, meter_id, datetime, 
						energy_purchased, energy_sold)
					VALUES (?, ?, ?, ?, ?)
				''', (
					id_order,
					meter_id,
					dt,
					results['e_pur_pool'][meter_id][idx],
					results['e_sale_pool'][meter_id][idx]
				))

		conn.commit()

		logger.info('[THREAD] Finished!')
