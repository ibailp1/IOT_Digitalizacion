Desde la instancia EC2 (Linux/Unix)



Hay que añadir una "Inbound Rule" en el Security Groups de tu instancia "launch-wizard-2" o el que sea (debes seleccionar el de tu instancia). Lo pone en el resúmen, y para acceder debes ir al panel izquierdo.



Añade uan regla de tipo TCP personalizado, con el Puerto que hayas configurado en Flask (5000 o 5001), y el Source debe ser Anywhere-IPv4. OJO con no modificar la regla ya existente, porque no te dejará conectarte a la instancia mediante SSH.



Copia los archivos a la instancia mediante SCP. Utiliza la script "copier.bat".



La script "copier.bat" Tiene dos modos. Puedes copiar el servidor web a cloud y lo otro a master. Es el primer parámetro (cloud / master). El Segundo parámetro es la IP.



copiar.bat cloud 123.123.123.123



Y desde la instancia, hay que instalar estas cosas:



sudo dnf install python3-pip

python3 -m pip install flask

python3 -m pip install awsiotsdk



Para ejecutar la app, desde /home/ec2-user/casa-iot/cloud:



python3 app.py



