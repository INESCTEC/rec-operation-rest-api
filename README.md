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


> **_NOTE:_** This software is on active development and depends on an extra Python Library (which will be uploaded soon to this GitHub Organization).


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