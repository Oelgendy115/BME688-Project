currently getting erros and warnings when trying to setup with the bsec libary. 

found out from the BSEC integration guide stored in the Important docs file that there different configs for the sensor one called sel and the other for IAQ 

currently there are 2 that i am intersted in



bme688_sel_33v_300s_4d  




i am trying to load the ai config profiles dynamically and intilizing the code correctly so the sensors work. added a new way using json need to check if it works 


adjusted the code so it can read config files from the sdcard and now you can easily change the config for the sensors


added duty cycles to match the code in