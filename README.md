![alt text](figures/logo_Enershare.png)
```
  _____                          _                                 ____   _____  ____   _      _____  __  __   ____         _        _                    _     ____  ___ 
 | ____| _ __    ___  _ __  ___ | |__    __ _  _ __  ___          |  _ \ | ____|/ ___| | |    | ____||  \/  | |  _ \  _ __ (_)  ___ (_) _ __    __ _     / \   |  _ \|_ _|
 |  _|  | '_ \  / _ \| '__|/ __|| '_ \  / _` || '__|/ _ \  _____  | |_) ||  _| | |     | |    |  _|  | |\/| | | |_) || '__|| | / __|| || '_ \  / _` |   / _ \  | |_) || | 
 | |___ | | | ||  __/| |   \__ \| | | || (_| || |  |  __/ |_____| |  _ < | |___| |___  | |___ | |___ | |  | | |  __/ | |   | || (__ | || | | || (_| |  / ___ \ |  __/ | | 
 |_____||_| |_| \___||_|   |___/|_| |_| \__,_||_|   \___|         |_| \_\|_____|\____| |_____||_____||_|  |_| |_|    |_|   |_| \___||_||_| |_| \__, | /_/   \_\|_|   |___|
                                                                                                                                               |___/                      
```
Welcome to INESC TEC Renewable Energy Community (REC) Local Energy Market (LEM) pricing API.

This REST API provides endpoints for calculating **optimal LEM prices for REC** under the *Enershare* project.


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