@ECHO OFF

SETLOCAL

SET "cosa=%~1"

IF NOT DEFINED cosa (

	ECHO [ERROR] Falta especificar el parámetro #1: La cosa que vas a copiar: "cloud" o "master" ^(con o sin comillas^)

	ENDLOCAL

	EXIT /B 1

)

IF NOT "%cosa%"=="cloud" IF NOT "%cosa%"=="master" (

	ECHO [ERROR] Parámetro #1: La cosa que vas a copiar debe ser una de estas dos: "cloud" o "master" ^(con o sin comillas^)

	EXIT /B 1

)

SET "direccion_ip=%~2"

IF NOT DEFINED direccion_ip (

	ECHO [ERROR] Falta especificar el parámetro #2: La dirección IP pública de la instancia EC2 / de la Raspberry.

	ENDLOCAL

	EXIT /B 1

)

SET "ruta_subcarpeta=%~3"
SET "ruta_archivo=%~4"

SET "ruta_origen=%CD:\=/%/%cosa%/"
SET "ruta_destino=/home/ec2-user/casa-iot/"

SET "parametros_scp="

IF DEFINED ruta_subcarpeta (

	IF NOT DEFINED ruta_archivo (

		ECHO [ERROR] La ruta especificada en el parámetro #3 ^(opcional^) se asume que es un directorio, y debe ir acompañada de un parámetro #4 para que SCP no haga de las suyas.

		ENDLOCAL

		EXIT /B 1

	)

	SET "ruta_origen=%ruta_origen%%ruta_subcarpeta%/%ruta_archivo%"
	SET "ruta_destino=%ruta_destino%%cosa%/%ruta_subcarpeta%/%ruta_archivo%"

) ELSE (

	SET "parametros_scp=-r"

)

SET "ruta_archivo_pem=../casa-iot-%cosa%.pem"

IF NOT EXIST %ruta_archivo_pem% (

	ECHO [ERROR] El archivo PEM para conectarse con la instancia EC2 a través de SSH debe encontrarse en esta ruta relativa: %ruta_archivo_pem%

	ENDLOCAL

	EXIT /B 1

)

scp -i "%ruta_archivo_pem%" %parametros_scp% "%ruta_origen%" ec2-user@%direccion_ip%:"%ruta_destino%"

ENDLOCAL
