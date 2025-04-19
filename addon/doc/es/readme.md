# Complemento Recordatorios para NVDA

Este complemento permite a los usuarios añadir recordatorios de manera sencilla, recibiendo notificaciones mediante un sonido de NVDA o sonidos personalizados cuando llegue la hora programada.

## Funcionalidades principales

- Crear recordatorios con mensajes personalizados
- Programar recordatorios para fechas y horas específicas
- Configurar recordatorios recurrentes (diarios, semanales, mensuales o personalizados)
- Utilizar sonidos personalizados para las notificaciones
- Administrar fácilmente los recordatorios activos

## Uso del complemento

El complemento incluye tres gestos sin asignar en los gestos de entrada de NVDA, bajo la categoría "Recordatorios":

### 1. Crear un nuevo recordatorio

Esta opción abre la ventana de configuración para añadir uno o más recordatorios. Al abrir la ventana, el foco se situará automáticamente en el campo para escribir el mensaje del recordatorio.

#### Configuración del recordatorio:

- **Mensaje**: Introduce el texto que deseas recibir como recordatorio.
- **Selección de fecha** (opcional):
  - Marca la casilla de verificación para programar el recordatorio en un día específico.
  - Al activarla, aparecerá un selector de fecha donde podrás elegir el día deseado.
  - Utiliza las flechas izquierda/derecha para moverte entre día, mes y año.
  - Utiliza las flechas arriba/abajo para modificar los valores.
  - La fecha se actualiza automáticamente al modificar los valores.
- **Hora**: Selecciona la hora en formato 24 horas mediante el primer cuadro combinado.
- **Minutos**: Selecciona los minutos en el segundo cuadro combinado.
- **Recordatorio recurrente**:
  - Marca esta casilla si deseas que el recordatorio se repita.
  - Al activarla, aparecerá un cuadro combinado donde podrás seleccionar la frecuencia: diaria, semanal, mensual o personalizada.
- **Sonido personalizado**:
  - Marca esta casilla si deseas usar un sonido diferente al estándar de NVDA.
  - Al activarla, se mostrarán las siguientes opciones:
    - Un cuadro combinado con los sonidos disponibles (archivos .wav).
    - Un botón para reproducir el sonido seleccionado.
    - Un botón para seleccionar la carpeta de sonidos personalizados.

Una vez configurado todo según tus preferencias, pulsa el botón "Agregar recordatorio" para guardarlo. Los recordatorios se almacenan en un archivo "recordatorios.json" en la carpeta de usuario de NVDA. Adicionalmente, se genera un archivo "sonidos_recordatorios.json" que guarda la ruta de la carpeta de sonidos seleccionada para futuros recordatorios.

### 2. Consultar recordatorios activos

Esta opción muestra una ventana explorable donde podrás revisar todos los recordatorios configurados. Utiliza las teclas de flecha para desplazarte por la lista y consultar los detalles de cada recordatorio junto con su programación.

### 3. Eliminar recordatorios

Esta opción abre un diálogo de selección que te permite elegir y eliminar los recordatorios que ya no necesites.

## Acceso desde el menú Herramientas de NVDA

Después de instalar el complemento, se añade un submenú en la sección de Herramientas de NVDA con las siguientes opciones:

- Añadir recordatorio
- Ver recordatorios activos
- Eliminar recordatorio

Si seleccionas "Eliminar recordatorio" y tienes recordatorios configurados, se abrirá una lista con todos ellos para que selecciones cuál deseas eliminar. Si no hay recordatorios activos, se mostrará un mensaje informativo. Lo mismo ocurre con la opción para ver recordatorios activos.

## Configuración del complemento

En el menú Preferencias > Opciones de NVDA, encontrarás una nueva categoría llamada "Configuración de Recordatorios" con las siguientes opciones:

- **Número de notificaciones**: Define cuántas veces se repetirá la notificación de cada recordatorio.
- **Intervalo de notificaciones**: Establece el tiempo entre notificaciones consecutivas (5, 10 o 20 segundos).

## Sugerencias y contacto

Si deseas hacer alguna sugerencia para mejorar el complemento, puedes enviar un correo a la siguiente dirección:

[contacto@marco-ml.com](mailto:contacto@marco-ml.com)

## Historial de versiones

- **Versión 1.3**: Implementación de recordatorios para fechas específicas.
- **Versión 1.2**: Preparación del complemento para su distribución en la tienda de nvda.es.
- **Versión 1.1**: Añadida la personalización de la recurrencia de los recordatorios (en minutos).
- **Versión 1.0**: Versión inicial con todas las funcionalidades básicas.