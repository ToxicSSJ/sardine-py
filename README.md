# 🐟 SardinePY

SardinePY es el proyecto resultado del primer proyecto de Topicos de Telematica, es entonces una implementación de una red P2P utilizando el protocolo HTTP creado en Python 3.9 y Flask. Se basa en una implementación de un P2P centralizado donde el nodo central es llamado (master) y permite conectar a los nodos hijos llamados (server) entre ellos. SardinePY permite subir archivos de manera completa o particionada a un nodo conectado a la red, descargarlos independientemente si están o no particionados, removerlos y listarlos.

> Para la transferencia de datos se optó por encodear los bytes a transferir en Base64 tanto para peticiones como para respuestas. Asimismo también se utiliza TinyDB para manejar una pequeña base de datos que simula la estructura propuesta <k, v> donde k es el hash SHA256 del archivo subido a la red.

### Endpoints (HTTP) - Nodo Server

- GET    `/ping` – Permite ver el estado del servidor
- GET    `/list` - Permite listar los archivos
- GET    `/space/<bytes>` - Permite conocer si el servidor está disponible para recibir X cantidad de bytes
- GET    `/find/<hash>` - Permite buscar un archivo por su hash
- GET    `/master/find/<hash>` - Permite buscar un archivo en toda la red por su hash
- GET    `/master/space/<bytes>` - Permite conocer todos los nodos hijos que tienen una capacidad X de bytes disponibles
- PUT    `/upload` - Permite subir un archivo via base64 de forma completa sin particiones
- PUT    `/chunks/upload` - Permite subir un archivo via base64 con una partición definida
- PUT    `/master/single/upload` - Permite subir un archivo via base64 de forma completa sin particiones en el "primer" nodo servidor proveido por la red con la capacidad suficiente y disponible para subir el archivo
- PUT    `/master/chunks/upload` - Permite subir un archivo via base64 de forma completa con particiones automaticas en los nodos que tengan la capacidad suficiente para contener cada uno de los chunks realizados
- GET    `/download/<hash>` - Permite descargar un archivo en base a su hash
- GET    `/chunks/download/<hash>/<index>` - Permite descargar un chunk de un archivo en base a su hash y su indice
- GET    `/master/single/download/<hash>` - Permite descargar un archivo completo basandose en su hash
- GET    `/master/chunks/download/<hash>` - Permite descargar un archivo completo basandose en su hash utilizando nodos que contengan los chunks del archivo, para ello se buscara cada pieza por medio de la red master y a medida se van descargando se va armando el resultado final
- DELETE `/remove/<hash>` – Permite remover un archivo de la base de datos <k, v> donde k es el valor.

### Endpoints (HTTP) - Nodo Master

- GET    `/ping` – Permite ver el estado del servidor central master
- GET    `/register/<server>` - Permite registrar un nodo servidor al servidor central dandole conocimiento a este de su ubicación en la red
- GET    `/unregister/<server>` - Permite remover un nodo servidor al servidor central
- GET    `/space/<bytes>` - Permite conocer todos los nodos hijos que tienen una capacidad X de bytes disponibles
- GET    `/find/<hash>` - Permite buscar un archivo en toda la red por su hash (independientemente si es tipo unico o particionado)

### Tecnologias Utilizadas

- Python 3.9
- Flask
- Bottle
- Requests
- TinyDB

### Desarrolladores
- Abraham M. Lora
- Yoban S. Novaa