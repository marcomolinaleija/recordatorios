# Recordatorios

Este complemento permite al usuario añadir recordatorios de manera sencilla, notificando mediante un sonido de NVDA o un sonido personalizado cuando llegue la hora programada.

## Uso del complemento

El complemento incluye 3 gestos sin asignar en los gestos de entrada de NVDA, bajo la categoría "Recordatorios":

### 1. Abrir la ventana para añadir un recordatorio

Esta opción te permitirá añadir uno o más recordatorios. Al abrir la ventana, automáticamente estarás enfocado en el cuadro para escribir el mensaje del recordatorio. 

- **Configuración del recordatorio**: 
  - Después de escribir tu mensaje, encontrarás dos cuadros combinados. El primero te permitirá seleccionar la hora en formato de 24 horas, y el segundo, los minutos. Puedes modificar estos valores según tus necesidades.
  - También hay 2 casillas de verificación, que están desmarcadas por defecto. La primera pregunta si el recordatorio será recurrente. Al activarla, aparecerá un cuadro combinado donde podrás seleccionar la frecuencia: diaria, semanal, mensual o personalizada.
  - La segunda casilla, que también está desmarcada por defecto, te preguntará si deseas añadir un sonido personalizado para el recordatorio. Al marcarla, se mostrarán más opciones.

- **Sonidos personalizados**: 
  - La primera opción será un cuadro combinado que cargará los sonidos de la carpeta que hayas seleccionado. Solo se cargarán los archivos con extensión .wav.
  - La segunda opción es un botón para reproducir el sonido seleccionado en el cuadro anterior, permitiéndote obtener una escucha previa antes de confirmar tu elección.
  - Por último, encontrarás un botón para seleccionar la carpeta de sonidos, lo que te permitirá cargar los sonidos disponibles en el cuadro de selección.

Una vez que hayas configurado todos los elementos de acuerdo a tus preferencias, simplemente presiona el botón "Agregar recordatorio" para guardarlo. Los recordatorios se almacenan en un archivo llamado "recordatorios.json" en la carpeta de usuario de NVDA. Además, se genera un archivo adicional llamado "sonidos_recordatorios.json", que facilitará la carga de la carpeta de sonidos seleccionada. Esto significa que, al reiniciar NVDA o apagar y encender la PC nuevamente, la carpeta de sonidos ya estará disponible para que puedas elegir un sonido personalizado para tu recordatorio sin tener que seleccionar la carpeta nuevamente.

### 2. Verificar recordatorios activos

Esta opción te permitirá revisar los recordatorios que has configurado. Al seleccionar esta opción, se abrirá una ventana explorable donde podrás desplazarte con las flechas para revisar los recordatorios junto con su hora programada.


### 3. Lansar el diálogo para eliminar recordatorios

Esto abrirá un diálogo de selección para que elimines un recordatorio

## Menú herramientas de NVDA

Después de instalar correctamente el complemento, también se añadirá un menú en la sección de herramientas con las siguientes opciones:

- Añadir recordatorio
- Ver recordatorios activos
- Eliminar recordatorio

La única opción que cambia aquí es la de eliminar recordatorio. Al seleccionar esta opción, si tienes recordatorios configurados, se abrirá una lista con los nombres de los mismos para que puedas eliminar alguno. Si no tienes recordatorios activos, aparecerá un mensaje que te informará que no se han encontrado recordatorios configurados.

## Configuraciones del complemento

En el menú de preferencias > opciones de NVDA, se creará una nueva categoría llamada "Configuración de Recordatorios". Esta categoría contiene las siguientes opciones:

- **Número de notificaciones**: El primer cuadro te solicitará seleccionar el número de notificaciones que llegarán para el recordatorio.
  
- **Intervalo de notificaciones**: El segundo cuadro te pedirá que establezcas el intervalo entre las notificaciones. Si, por ejemplo, seleccionaste 2 veces en el cuadro anterior, este intervalo determinará cada cuántos segundos recibirás esas notificaciones, pudiendo elegir intervalos de 5, 10 o 20 segundos.

# Sugerencias

Si deseas hacer alguna sugerencia para el complemento, puedes enviar un correo a la siguiente dirección:

[correo electrónico](mailto:marcomolinaleija@hotmail.com)

# Historial de versiones

- **Versión 1.1**: Se añade la posibilidad de poder personalizar la recurrencia de los recordatorios (En minutos)

- **Versión 1.0**: Versión inicial del complemento, que contiene todas las opciones descritas anteriormente.

---

Y eso es todo por ahora. Muchas gracias por descargar, instalar y probar este complemento.