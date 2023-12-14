# Instalación del RTC externo en DietPi

1. Copiar el archivo `sun8i-h3-mcp7940x.dtbo` en la carpeta `/boot/dtb/overlay/`

2. Editar el archivo `/boot/dietpiEnv.txt` y agregar `uart1 uart2 i2c0 mcp7940x` en la entrada `overlays`

3. En `dietpi-config`, en el menú _4 - Advanced options_, en el submenú _RTC mode_ elegir la opción _Hardware_
