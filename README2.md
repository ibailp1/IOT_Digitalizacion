\#EXPLICACIÓN



He simplificado el código para cumplir con los requisitos de la entrega, ya que no me parece necesario mantener toda la infraestructura digital si no se utiliza.



La idea principal es que se le solicite al Arduino el estado de los sensors y actuadores que estamos utilizando, una única vez, y a partir de ahí el Arduino toma la iniciativa de enviar información adicional cuando el estado cambia. Así evitamos saturar la casa con peticiones.



El Arduino envía información de manera selectiva. En lugar de parsear cadenas de texto, he decidido hacerlo con JSON. Puede que el objeto contenga solo el estado de la luz amarilla, o el de varias. La estructura completa del objeto no cambia, pero sí que pueden faltar propiedades. Eso significa simplemente que no hay información nueva. Sólo hace falta actualizar lo justo y necesario.



El Arduino envía el JSON en forma de spaguetti, que es muchísimo más fácil de parsear y de generar. Los comandos que se le envían al Arduino son más simples y están en forma de comando (cadena de texto sencilla en una única línea).



No hace falta ninguna librería especial para generar el JSON desde el Arduino. Basta con unos bucles y unas string. De hecho, cada sensor envía datos individuales, así que se simplifica mucho la lógica para construir el objeto.



En lugar de hacer un bucle que constantemente comprueba si hay información nueva, he utilziado el módulo "selectors" de Python, basado en eventos, para que el sistema operativo notifique a la Raspberry en el momento que haya tráfico en el descriptor de archivo del serial.



La app web también funciona por eventos. Cuando recibe una publicación MQTT mediante AWS IOT Core, mete la carga útil en una cola, y en el bucle principal, antes de encender la aplicación, ejecuta un hilo en paralelo que escucha eventos en esa cola de publicaciones, procesando cada publicación cada vez que se mete en la cola (cuando llega una publicación MQTT).



He decidido que la app web no almacenará los datos de dybamodb en un archivo local, sino que directamente carga en memoria los datos que necesita. Tambien, en lugar de generar el timestamp en el momento de leer la telemetría de la DB, lo genero desde la Raspberry cuando la recibe del Arduino.



Al cargar la app web, leemos desde dynamodb la telemetría de las últimas 24 horas, y cada vez que llegue telemetría nueva, notificamos al cliente web (que estará esperando con un fetch).





\#CONFIGURACIÓN



Desde la instancia EC2 (Linux/Unix)



Hay que añadir una "Inbound Rule" en el Security Groups de tu instancia "launch-wizard-2" o el que sea (debes seleccionar el de tu instancia). Lo pone en el resúmen, y para acceder debes ir al panel izquierdo.



Añade uan regla de tipo TCP personalizado, con el Puerto que hayas configurado en Flask (5000 o 5001), y el Source debe ser Anywhere-IPv4. OJO con no modificar la regla ya existente, porque no te dejará conectarte a la instancia mediante SSH.



Copia los archivos a la instancia mediante SCP. Utiliza la script "copier.bat".



La script "copier.bat" Tiene dos modos. Puedes copiar el servidor web a cloud y lo otro a master. Es el primer parámetro (cloud / master). El Segundo parámetro es la IP.



Puedes especificar en un tercer parámetro la ruta relativa a "repo/cloud/" para especificar una carpeta y un cuarto paráemtro para el nombrer del archivo, y así copiar solo un archivo (es mucho más rápido, útil mientras haces pequeños cambios durante el desarrollo).



Si quieres un único archivo de la carpeta raíz (cloud o master), pon "/" en el tercer parámetro (no hacen falta comillas).



Ejecuta este comando desde la instancia para saber la IP:

curl ifconfig.me



copiar.bat cloud 123.123.123.123



Y desde la instancia, hay que instalar estas cosas:



sudo dnf install python3-pip

python3 -m pip install flask

python3 -m pip install awsiotsdk

python3 -m pip install boto3



Para ejecutar la app, desde /home/ec2-user/casa-iot/cloud:



python3 app.py

