@ECHO OFF

SETLOCAL

SET "nombre_usuario=%~1"

IF NOT DEFINED nombre_usuario (

	ECHO [ERROR] Falta especificar el parámetro #1: El nombre de usuario remoto.

	ENDLOCAL

	EXIT /B 1

)

SET "parametros_scp="

SET ruta_archivo_pem="../ec2-user-casa-iot-cloud.pem"

IF "%nombre_usuario%"=="ec2-user" (

	IF NOT EXIST %ruta_archivo_pem% (

		ECHO [ERROR] El archivo PEM para conectarse con la instancia EC2 a través de SSH debe encontrarse en esta ruta relativa: %ruta_archivo_pem%

		ENDLOCAL

		EXIT /B 1

	)

	SET "parametros_scp=-i %ruta_archivo_pem%"

)

SET "parametros_scp=%parametros_scp% -r"

SET "direccion_ip=%~2"

IF NOT DEFINED direccion_ip (

	ECHO [ERROR] Falta especificar el parámetro #2: La dirección IP pública de la instancia EC2 / de la Raspberry.

	ENDLOCAL

	EXIT /B 1

)

SET "ruta_origen=%CD:\=/%/../secretos/"
SET "ruta_destino=/home/%nombre_usuario%/casa-iot/"

scp %parametros_scp% "%ruta_origen%" %nombre_usuario%@%direccion_ip%:"%ruta_destino%"

ENDLOCAL

EXIT /B 0
