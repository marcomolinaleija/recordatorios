# Complemento Recordatorios para NVDA

Este complemento permite a los usuarios añadir recordatorios de manera sencilla, recibiendo notificaciones mediante un sonido de NVDA o sonidos personalizados cuando llegue la hora programada.

## Funcionalidades principales

* Crear recordatorios con mensajes personalizados y listas de tareas.
* Programar recordatorios para fechas y horas específicas.
* Configurar recordatorios recurrentes (diarios, semanales, mensuales o personalizados).
* Utilizar sonidos personalizados para las notificaciones.
* Administrar fácilmente los recordatorios activos (ver, eliminar, reprogramar y gestionar tareas).
* Diálogo interactivo para recordatorios con tareas pendientes, con opciones para posponer o eliminar.

## Uso del complemento

El complemento añade un submenú "Recordatorios" en el menú Herramientas de NVDA y permite asignar gestos de entrada para las siguientes acciones:

### 1. Añadir un nuevo recordatorio

Esta opción abre la ventana de configuración para añadir uno o más recordatorios. Al abrir la ventana, el foco se situará automáticamente en el campo para escribir el mensaje del recordatorio.

#### Configuración del recordatorio:

* **Mensaje**: Introduce el texto que deseas recibir como recordatorio.
* **Tareas**: En el campo multilínea, puedes añadir tareas asociadas, una por línea.
* **Selección de fecha** (opcional):
    * Marca la casilla de verificación para programar el recordatorio en un día específico.
    * Al activarla, aparecerá un selector de fecha donde podrás elegir el día deseado.
    * Utiliza las flechas izquierda/derecha para moverte entre día, mes y año.
    * Utiliza las flechas arriba/abajo para modificar los valores.
* **Hora**: Selecciona la hora en formato 24 horas.
* **Minutos**: Selecciona los minutos.
* **Recordatorio recurrente**:
    * Marca esta casilla si deseas que el recordatorio se repita.
    * Al activarla, aparecerá un cuadro combinado donde podrás seleccionar la frecuencia: diaria, semanal, mensual o personalizada.
* **Sonido personalizado**:
    * Marca esta casilla si deseas usar un sonido diferente al estándar de NVDA.
    * Al activarla, se mostrarán las opciones para seleccionar una carpeta de sonidos, elegir un archivo `.wav` y reproducirlo.

Una vez configurado todo, pulsa el botón "Agregar recordatorio" para guardarlo.

### 2. Consultar, eliminar, reprogramar y gestionar tareas

Desde el submenú "Recordatorios" en Herramientas, tienes acceso a:

* **Ver Recordatorios Activos**: Muestra una ventana explorable con todos los detalles de tus recordatorios, incluyendo el tiempo restante y el estado de las tareas.
* **Eliminar Recordatorio**: Abre un diálogo para seleccionar y eliminar los recordatorios que ya no necesites.
* **Reprogramar Recordatorio**: Permite elegir un recordatorio y asignarle una nueva fecha y hora.
* **Gestionar Tareas**: Abre un diálogo para marcar o desmarcar las tareas de un recordatorio como completadas.

### 3. Manejo de Tareas Incompletas (¡Nuevo!)

Cuando un recordatorio **no recurrente** llega a su hora y tiene tareas sin completar, ya no se elimina automáticamente. En su lugar, aparece un nuevo diálogo con las siguientes opciones:

* **Eliminar de todos modos**: Descarta el recordatorio permanentemente.
* **Revisar tareas (posponer 10 min)**: Pospone el recordatorio por 10 minutos, dándote tiempo para gestionar las tareas desde el menú "Herramientas".
* **Posponer...**: Abre un segundo diálogo donde puedes introducir un número de minutos personalizado para posponer el recordatorio.

Si cierras el diálogo sin elegir una opción, el recordatorio se guarda para que no pierdas la información.

## Configuración del complemento

En el menú Preferencias > Opciones de NVDA, encontrarás una nueva categoría llamada "Configuración de Recordatorios" con las siguientes opciones:

* **Número de notificaciones**: Define cuántas veces se repetirá la notificación de cada recordatorio.
* **Intervalo de notificaciones**: Establece el tiempo en segundos entre notificaciones consecutivas.

## Sugerencias y contacto

Si deseas hacer alguna sugerencia para mejorar el complemento, puedes enviar un correo a la siguiente dirección:
[contacto@marco-ml.com](mailto:contacto@marco-ml.com)

## Historial de versiones

* **Versión 1.4**: Manejo mejorado para recordatorios con tareas incompletas. Ahora, cuando un recordatorio no recurrente con tareas pendientes llega a su hora, se muestra un diálogo con opciones para eliminar, posponer por 10 minutos, o posponer por un tiempo personalizado, evitando que se elimine automáticamente.
* **Versión 1.3**: Implementación de recordatorios para fechas específicas.
* **Versión 1.2**: Preparación del complemento para su distribución en la tienda de nvda.es.
* **Versión 1.1**: Añadida la personalización de la recurrencia de los recordatorios (en minutos).
* **Versión 1.0**: Versión inicial con todas las funcionalidades básicas.