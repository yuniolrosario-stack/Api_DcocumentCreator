# Guía Rápida para Probar la API en Postman

He preparado la colección oficial preconfigurada en el archivo:
📁 **[FirmaGOB_Postman_Collection.json](file:///c:/Users/onix0/Desktop/API%20Creator%20Document/FirmaGOB_Postman_Collection.json)**

Esta colección tiene **scripts automáticos integrados**: cuando ejecutas la petición 1 (Iniciar Firma), Postman guarda automáticamente el `trackingId`, `publicAccessId` y `documentId` devueltos, por lo que **no tienes que copiar y pegar identificadores a mano** para consultar el estado o descargar el PDF.

---

## 📥 Paso 1: Importar en Postman

1. Abre **Postman**.
2. Haz clic en el botón **Import** (esquina superior izquierda).
3. Selecciona o arrastra el archivo:
   `c:\Users\onix0\Desktop\API Creator Document\FirmaGOB_Postman_Collection.json`
4. Verás la nueva colección llamada:
   **"Firma GOB (OGTIC) - Integración Firma Desatendida & Callback"**

---

## 🚀 Paso 2: Probar los Endpoints en Orden

La colección contiene 6 peticiones organizadas secuencialmente:

### 1. `0. Health Check` (GET `http://localhost:8000/api/health`)
- **Propósito:** Confirmar que la API está encendida.
- **Respuesta esperada:** `HTTP 200 OK` con `"status": "healthy"`, `"mock_server_enabled": true`.

---

### 2. `1. Iniciar Firma Desatendida` (POST `http://localhost:8000/api/v1/documents/sign`)
- **Propósito:** Envía el payload JSON oficial con un PDF de prueba en Base64.
- **Respuesta esperada:** `HTTP 201 Created`
  ```json
  {
    "success": true,
    "trackingId": "3c7a6c0c-b71d-4085-91a3-f1390416972f",
    "firmagob": {
      "code": "MOCK-...",
      "publicAccessId": "PAID-...",
      "documentId": "DOC-...",
      "status": "IN_PROCESS"
    }
  }
  ```
- **Magia automática:** El script de Postman captura `trackingId` y `publicAccessId` para las siguientes peticiones.
- **Flujo en background:** Tras 2 segundos, el simulador del HSM disparará automáticamente el webhook callback completando la firma.

---

### 3. `2. Consultar Detalle y Estado` (GET `http://localhost:8000/api/v1/documents/{{trackingId}}`)
- **Propósito:** Verifica el estado en tiempo real.
- **Respuesta esperada:** `HTTP 200 OK`
  - Primeros 2 segundos: `"status": "IN_PROCESS"`, `"hasSignedFile": false`.
  - Pasados 2 segundos: `"status": "COMPLETED"`, `"hasSignedFile": true`.

---

### 4. `3. Simular Webhook Callback` (POST `http://localhost:8000/api/v1/firmagob/callback`)
- **Propósito:** Probar manualmente el Endpoint 2 de OGTIC:
  ```json
  {
    "publicAccessId": "{{publicAccessId}}",
    "action": "SIGN",
    "status": "COMPLETED"
  }
  ```
- **Respuesta esperada:** `HTTP 200 OK` con `{ "result": "ok" }` en `< 50ms`.

---

### 5. `4. Descargar Documento Firmado` (GET `http://localhost:8000/api/v1/documents/{{trackingId}}/download`)
- **Propósito:** Descarga el binario PDF firmado con el sello digital estampado.
- **En Postman:** Haz clic en la flechita junto a **Send** y elige **"Send and Download"** para guardar el archivo `.pdf` en tu computadora y abrirlo en Adobe Acrobat / visor de PDF.

---

### 6. `5. Listar Todas las Solicitudes` (GET `http://localhost:8000/api/v1/documents?limit=20`)
- **Propósito:** Retorna la lista histórica de solicitudes procesadas.
- **Respuesta esperada:** `HTTP 200 OK` con el listado completo y paginación.

---

### 7. `6. Subida Directa de PDF (Multipart Form Data)`
- **Propósito:** Si deseas firmar un archivo PDF real desde tu disco duro sin codificarlo manualmente en Base64.
- **En Postman:** Pestaña **Body** -> **form-data** -> Selecciona cualquier archivo PDF en el campo `file` y pulsa **Send**.

---

## 💡 Opción Alternativa: Importar OpenAPI directo
También puedes importar la especificación OpenAPI en vivo directamente en Postman:
- En Postman: **Import** -> Introduce la URL: `http://localhost:8000/openapi.json`
