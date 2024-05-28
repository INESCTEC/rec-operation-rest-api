import os
import sqlite3


def connect_to_sqlite_db() -> (sqlite3.Connection, sqlite3.Cursor):
    """
    Function to return the connection and cursor to the SQLite database.
    :return:
    """
    # Define the path to the database file
    db_path = r'helpers/orders.db'

    # Connect to the SQLIte database
    # If the database doesn't exist, it will be created
    conn = sqlite3.connect(db_path, check_same_thread=False)
    curs = conn.cursor()

    # Check if the database file just got created
    if os.path.getsize(db_path) == 0:
        # The database file did not exist before, so we need to create the tables

        # TO STORE ORDERS ##############################################################################################
        # Create the Orders table
        curs.execute('''
        CREATE TABLE Orders (
        order_id TEXT PRIMARY KEY,
        processed BOOLEAN,
        error TEXT,
        message TEXT,
        request_type TEXT,
        lem_organization TEXT,
        pricing_mechanism TEXT
        )
        ''')

        # TO STORE VANILLA OUTPUTS #####################################################################################
        # Create the Lem_Prices table
        curs.execute('''
        CREATE TABLE Lem_Prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        datetime TEXT,
        value REAL,
        FOREIGN KEY(order_id) REFERENCES Orders(order_id)
        )
        ''')

        # Create the Offers table
        curs.execute('''
        CREATE TABLE Offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        datetime TEXT,
        meter_id TEXT,
        amount REAL,
        value REAL,
        type TEXT,
        FOREIGN KEY(order_id) REFERENCES Orders(order_id)
        )
        ''')

        # TO STORE MILP OUTPUTS ########################################################################################
        # Create the General_MILP_Outputs, for single scalar values + the status of the MILP solution
        curs.execute('''
        CREATE TABLE General_MILP_Outputs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        objective_value REAL,
        milp_status TEXT,
        total_rec_cost REAL,
        FOREIGN KEY(order_id) REFERENCES Orders(order_id)
        )
        ''')

        # Create the Individual_Costs, for outputs that are dependent on the meter ID but not time-varying
        curs.execute('''
        CREATE TABLE Individual_Costs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        meter_id TEXT,
        individual_cost REAL,
        FOREIGN KEY(order_id) REFERENCES Orders(order_id)
        )
        ''')

        # Create the Meter_Inputs, for the meter-dependent, time-varying inputs used to feed the MILP
        curs.execute('''
        CREATE TABLE Meter_Inputs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        meter_id TEXT,
        datetime TEXT,
        energy_generated REAL,
        energy_consumed REAL,
        buy_tariff REAL,
        sell_tariff REAL,
        FOREIGN KEY(order_id) REFERENCES Orders(order_id)
        )
        ''')

        # Create the Meter_Outputs, for the meter-dependent, time-varying outputs from the MILP
        curs.execute('''
        CREATE TABLE Meter_Outputs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        meter_id TEXT,
        datetime TEXT,
        energy_surplus REAL,
        energy_supplied REAL,
        net_load REAL,
        bess_energy_charged REAL,
        bess_energy_discharged REAL,
        bess_energy_content REAL,
        FOREIGN KEY(order_id) REFERENCES Orders(order_id)
        )
        ''')

        # Create the Pool_LEM_Transactions, for aggregate buys and sells on LEM
        curs.execute('''
        CREATE TABLE Pool_LEM_Transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        meter_id TEXT,
        datetime TEXT,
        energy_purchased REAL,
        energy_sold REAL
        )
        ''')

        # Create the Bilateral_LEM_Transactions, for aggregate buys and sells on LEM
        curs.execute('''
        CREATE TABLE Bilateral_LEM_Transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        provider_meter_id TEXT,
        receiver_meter_id TEXT,
        datetime TEXT,
        energy REAL
        )
        ''')

        # Create the Pool_Self_Consumption_Tariffs, for the self-consumption tariffs fed to the MILP,
        # which are time-varying but not dependent on the meter ID
        curs.execute('''
        CREATE TABLE Pool_Self_Consumption_Tariffs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        datetime TEXT,
        self_consumption_tariff REAL,
        FOREIGN KEY(order_id) REFERENCES Orders(order_id)
        )
        ''')

        # Create the Bilateral_Self_Consumption_Tariffs, for the self-consumption tariffs fed to the MILP,
        # which are time-varying and  the meter ID
        curs.execute('''
       CREATE TABLE Bilateral_Self_Consumption_Tariffs (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       order_id TEXT,
       datetime TEXT,
       self_consumption_tariff REAL,
       provider_meter_id TEXT,
       receiver_meter_id TEXT,
       FOREIGN KEY(order_id) REFERENCES Orders(order_id)
       )
       ''')

    return conn, curs
