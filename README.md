![alt text](figures/logo_Enershare.png)
```
  _____   ______  _____    ____                            _    _                 _____   ______   _____  _______             _____  _____ 
 |  __ \ |  ____|/ ____|  / __ \                          | |  (_)               |  __ \ |  ____| / ____||__   __|     /\    |  __ \|_   _|
 | |__) || |__  | |      | |  | | _ __    ___  _ __  __ _ | |_  _   ___   _ __   | |__) || |__   | (___     | |       /  \   | |__) | | |  
 |  _  / |  __| | |      | |  | || '_ \  / _ \| '__|/ _` || __|| | / _ \ | '_ \  |  _  / |  __|   \___ \    | |      / /\ \  |  ___/  | |  
 | | \ \ | |____| |____  | |__| || |_) ||  __/| |  | (_| || |_ | || (_) || | | | | | \ \ | |____  ____) |   | |     / ____ \ | |     _| |_ 
 |_|  \_\|______|\_____|  \____/ | .__/  \___||_|   \__,_| \__||_| \___/ |_| |_| |_|  \_\|______||_____/    |_|    /_/    \_\|_|    |_____|
                                 | |                                                                                                       
                                 |_|                                                                                                                             
```
Welcome to INESC TEC Renewable Energy Community (REC) Operation API.

This REST API provides endpoints for the **optimal scheduling of REC controllable assets** and for calculating 
**optimal LEM prices and transactions** under the *Enershare* project.


> **_NOTE:_** This software is on active development and depends on an extra Python Library 
> (https://github.com/INESCTEC/rec-operation).


## Developers // Contacts:

* Ricardo Silva (ricardo.emanuel@inesctec.pt)


# Run API
Run the API locally with uvicorn:
```shell
$ uvicorn main:app 
```
(For development, you can include the ```--reload``` tag at the end).

# Swagger and Redoc
To access the interactive API docs, include the following at the end of the URL where uvicorn is running: 
- ```/docs``` (Swagger format);
- ```/redoc``` (ReDoc format);

# Docker
A dockerfile and docker-compose.yml file have been prepared for and 
easy deployment of the service on any server.

On a server with docker engine, docker-compose and git installed:

- clone this repository to the server;
- create the ```.env``` file on the project's base directory
- run the command ```docker-compose up -d --build``` (Windows) / 
```sudo docker compose up -d --build``` (Linux)

# Notes about hardcoded information
This API is specifically designed for interacting with the rec_operation library (https://github.com/INESCTEC/rec-operation) 
within the context of the ENERSHARE project. Several configurations required to describe the two REC within the project, 
SEL and IN-DATA are hardcoded. Given the sensitive nature of those static parameters, which includes the geographic 
location of the REC meters and the contracts celebrated with their respective retailers, the hardcoded values are 
fictitious. Such information can, nonetheless be edited in the following scripts:
- ```/helpers/indata_shelly_info.py``` ----- required configurations for requesting data from IN-DATA connector
- ```/helpers/meter_installed_pv.py``` ----- meters' installed PV capacity, in kWp
- ```/helpers/meter_locations.py``` -------- both RECs' geographic location, provided as latitude and longitude coordinates
- ```/helpers/meter_tariff_cycles.py``` ---- meters' contracted fixed tariff cycle, from ("simples", "bi-horárias", 
"tri-horárias")
- ```/helpers/sel_shelly_info.py``` -------- required configurations for requesting data from SEL connector