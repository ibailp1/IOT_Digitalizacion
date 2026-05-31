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

SET "nombre_usuario="
SET "parametros_scp="

SET ruta_archivo_pem="../ec2-user-casa-iot-cloud.pem"

IF "%cosa%"=="cloud" (

	SET "nombre_usuario=ec2-user"

	IF NOT EXIST %ruta_archivo_pem% (

		ECHO [ERROR] El archivo PEM para conectarse con la instancia EC2 a través de SSH debe encontrarse en esta ruta relativa: %ruta_archivo_pem%

		ENDLOCAL

		EXIT /B 1

	)

	SET "parametros_scp=-i %ruta_archivo_pem%"

)

IF "%cosa%"=="master" (

	SET "nombre_usuario=iot"

)

SET "parametros_scp=%parametros_scp% -r"

SET "direccion_ip=%~2"

IF NOT DEFINED direccion_ip (

	ECHO [ERROR] Falta especificar el parámetro #2: La dirección IP pública de la instancia EC2 / de la Raspberry.

	ENDLOCAL

	EXIT /B 1

)

SET "ruta_origen=%CD:\=/%/%cosa%/../../secretos/"
SET "ruta_destino=/home/%nombre_usuario%/casa-iot/"

scp %parametros_scp% "%ruta_origen%" %nombre_usuario%@%direccion_ip%:"%ruta_destino%"

ENDLOCAL

EXIT /B 0
