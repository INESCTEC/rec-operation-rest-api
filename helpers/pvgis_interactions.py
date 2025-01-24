import datetime
import pvlib
import pandas as pd


MAX_YEAR_PVGIS = 2023


def fetch_pvgis(start_dt: datetime.datetime,
                end_dt: datetime.datetime,
                latitude: float,
                longitude: float) -> pd.DataFrame:
    """
    Fetches for the given coordinates, and date in the past, the modeled PV power output from PVGIS.
    Data comes in W and the index is composed of datetime values with tz-awareness.
    :param start_dt:
    :param end_dt:
    :param latitude:
    :param longitude:
    :return: a pandas dataframe, with a datetime index, and PV generation factor estimates, with 15' time step
    """
    ####################################################################################################################
    # UNPACK
    ####################################################################################################################
    # year of first and last date in the dataframe
    # since PVGIS data is only available until MAX_YEAR_PVGIS,
    # assume that the generation profile on future dates is the same as in MAX_YEAR_PVGIS
    start = start_dt.year
    end = end_dt.year
    fetch_start = start if start <= MAX_YEAR_PVGIS else MAX_YEAR_PVGIS
    fetch_end = end if end <= MAX_YEAR_PVGIS else MAX_YEAR_PVGIS

    ####################################################################################################################
    # FETCH
    ####################################################################################################################
    # retrieve the data using the pvlib library
    pv_data, _, _ = pvlib.iotools.get_pvgis_hourly(
        latitude,
        longitude,
        start=fetch_start,
        end=fetch_end,
        raddatabase=None,
        components=True,
        surface_tilt=0,
        surface_azimuth=180,
        outputformat='json',
        usehorizon=True,
        userhorizon=None,
        pvcalculation=True,
        peakpower=1,
        pvtechchoice='crystSi',
        mountingplace='free',
        loss=0,
        trackingtype=0,
        optimal_surface_tilt=False,
        optimalangles=False,
        url='https://re.jrc.ec.europa.eu/api/',
        map_variables=True,
        timeout=30
    )

    ####################################################################################################################
    # PARSE
    ####################################################################################################################
    # prune the returned dataframe, keeping only the power timeseries
    pv_power_series = pv_data['P']
    pv_power_df = pv_power_series.to_frame(name='e_g')
    # resample the dataframe to 15' steps (originally in 1h steps)
    pv_power_df.reset_index(inplace=True)
    last_mock_row = pv_power_df.iloc[-1].to_dict()
    last_mock_row['time'] += pd.to_timedelta('60T')
    last_mock_row = pd.Series(last_mock_row).to_frame().T
    pv_power_df = pd.concat([pv_power_df, last_mock_row], ignore_index=True)
    pv_power_df.set_index('time', inplace=True)
    pv_power_df = pv_power_df.resample('15T').mean().ffill()
    pv_power_df = pv_power_df[:-1]
    # convert the time series from W to kW; since 1kWp was set as the installed capacity,
    # this can actually be translated directly to a PV generation factor
    pv_power_df['e_g'] /= 1000

    ####################################################################################################################
    # COMPLEMENT
    ####################################################################################################################
    # repeat the data fetched for MAX_YEAR_PVGIS if later years are included in the request,
    # defining that for later years, the same PV generation 15' profile found in MAX_YEAR_PVGIS is the best estimate
    if end > MAX_YEAR_PVGIS:
        yearly_data = pv_power_df.loc[pv_power_df.index.year == MAX_YEAR_PVGIS]
        for i in range(MAX_YEAR_PVGIS + 1, end + 1, 1):
            # update the year of the MAX_YEAR_PVGIS data
            new_index = [ts.replace(year=i) for ts in yearly_data.index]
            yearly_data.index = new_index
            # add the new yearly data to the original PV data dataframe
            pv_power_df = pd.concat([pv_power_df, yearly_data])

    ####################################################################################################################
    # PRUNE to requested start_dt and end_dt
    ####################################################################################################################
    pv_power_df = pv_power_df.loc[start_dt:end_dt-pd.to_timedelta('15T')]

    return pv_power_df
