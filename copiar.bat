@ECHO OFF

SET "cosa=%~1"

IF NOT DEFINED cosa (

	ECHO [ERROR] Falta especificar el parámetro #1: La cosa que vas a copiar: "cloud" o "master" ^(con o sin comillas^)

	EXIT /B 1

)

IF NOT "%cosa%"=="cloud" IF NOT "%cosa%"=="master" (

	ECHO [ERROR] Parámetro #1: La cosa que vas a copiar debe ser una de estas dos: "cloud" o "master" ^(con o sin comillas^)

	EXIT /B 1

)

SET "direccion_ip=%~2"

IF NOT DEFINED direccion_ip (

	ECHO [ERROR] Falta especificar el parámetro #2: La dirección IP pública de la instancia EC2 / de la Raspberry.

	EXIT /B 1

)

SET "ruta_archivo_pem=../casa-iot-nube.pem"

IF NOT EXIST %ruta_archivo_pem% (

	ECHO [ERROR] El archivo PEM para conectarse con la instancia EC2 a través de SSH debe encontrarse en esta ruta relativa: %ruta_archivo_pem%

	EXIT /B 1

)

scp -i "%ruta_archivo_pem%" -r "./%cosa%/" ec2-user@%direccion_ip%:/home/ec2-user/casa-iot/
