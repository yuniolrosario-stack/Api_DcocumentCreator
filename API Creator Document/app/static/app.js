// Sample PDF in Base64 (minimal valid single page PDF)
const DEFAULT_SAMPLE_PDF_B64 = 
  "JVBERi0xLjQKJcOkw7zDtsOfCjIgMCBvYmoKPDwvTGVuZ3RoIDMgMCBSL0ZpbHRlci9GbGF0ZURlY29kZT4+CnN0cmVhbQp4nCtUMF" +
  "DAAEZ0lFpKUWWlggpUQCw1sTgxLz1fISSxJFWhOD+3IDUvXUEvUcHJSUHRUFfRysDCwNxAQUkBCgQkghNLgCKlaakA3eAU6gplbmRz" +
  "dHJlYW0KZW5kb2JqCjMgMCBvYmoKMTA5CmVuZG9iagoxIDAgb2JqCjw8L1R5cGUvUGFnZS9QYXJlbnQgNCAwIFIvUmVzb3VyY2VzID" +
  "UgMCBSL01lZGlhQm94WzAgMCA2MTIgNzkyXS9Db250ZW50cyAyIDAgUj4+CmVuZG9iago1IDAgb2JqCjw8L1Byb2NTZXRbL1BERi9U" +
  "ZXh0XT4+CmVuZG9iago0IDAgb2JqCjw8L1R5cGUvUGFnZXMvQ291bnQgMS9LaWRzWzEgMCBSXT4+CmVuZG9iago2IDAgb2JqCjw8L1" +
  "R5cGUvQ2F0YWxvZy9QYWdlcyA0IDAgUj4+CmVuZG9iago3IDAgb2JqCjw8L1Byb2R1Y2VyKFJlcG9ydExhYik+PgplbmRvYmoKeHJl" +
  "ZgowIDgKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMjE2IDAwMDAwIG4gCjAwMDAwMDAwMTUgMDAwMDAgbiAKMDAwMDAwMDE5Ny" +
  "AwMDAwMCBuIAowMDAwMDAwMzI1IDAwMDAwIG4gCjAwMDAwMDAyOTAgMDAwMDAgbiAKMDAwMDAwMDM4MiAwMDAwMCBuIAowMDAwMDAw" +
  "NDI3IDAwMDAwIG4gCnRyYWlsZXIKPDwvU2l6ZSA4L1Jvb3QgNiAwIFIvSW5mbyA3IDAgUj4+CnN0YXJ0eHJlZgo0NzIKJSVFT0YK";

let selectedFile = null;

// Initial JSON payload exactly as provided by the user
const defaultPayload = {
  "sender": {
    "userCode": "40200000000",
    "entityCode": "default"
  },
  "addresseeLines": [
    {
      "addresseeGroups": [
        {
          "isOrGroup": false,
          "userEntities": [
            {
              "userCode": "40200000000",
              "entityCode": "default",
              "action": "SIGN"
            }
          ]
        }
      ]
    }
  ],
  "internalNotification": [],
  "subject": "Firma Desatendida de Documento Oficial",
  "message": "Solicitud generada automáticamente para firma en servidor.",
  "reference": "EXP-2026-00981",
  "verificationAccess": {
    "type": "ANONYMOUS"
  },
  "senderNotificationLevel": "ALL",
  "signatureLevel": "ALL",
  "notificationUrl": window.location.origin + "/api/v1/firmagob/callback",
  "callbackCode": "CALLBACK_INSTITUCIONAL_01",
  "useDefaultStamp": true,
  "documentsToSign": [
    {
      "filename": "Prueba_doc.pdf",
      "data": DEFAULT_SAMPLE_PDF_B64
    }
  ]
};

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("rawJsonInput").value = JSON.stringify(defaultPayload, null, 2);
  checkHealth();
  loadRequests();

  // Polling cada 3 segundos para refrescar el estado de las solicitudes
  setInterval(loadRequests, 3000);
});

function logMessage(text, type = "info") {
  const container = document.getElementById("activityLogs");
  const time = new Date().toLocaleTimeString();
  const entry = document.createElement("div");
  entry.className = `log-entry ${type}`;
  entry.textContent = `[${time}] ${text}`;
  container.appendChild(entry);
  container.scrollTop = container.scrollHeight;
}

function switchTab(tab) {
  const isUpload = tab === "upload";
  document.getElementById("tabUploadBtn").classList.toggle("active", isUpload);
  document.getElementById("tabJsonBtn").classList.toggle("active", !isUpload);
  document.getElementById("uploadForm").classList.toggle("active", isUpload);
  document.getElementById("jsonEditorTab").classList.toggle("active", !isUpload);
}

function handleFileSelected(input) {
  if (input.files && input.files[0]) {
    selectedFile = input.files[0];
    document.getElementById("fileLabel").textContent = `${selectedFile.name} (${(selectedFile.size / 1024).toFixed(1)} KB)`;
  }
}

async function checkHealth() {
  const pill = document.getElementById("connectionStatus");
  try {
    const res = await fetch("/api/health");
    if (res.ok) {
      const data = await res.json();
      pill.textContent = data.mock_server_enabled ? "Servidor Activo (Mock HSM)" : "Servidor Activo (OGTIC Live)";
      pill.className = "status-pill online";
    } else {
      pill.textContent = "Error de conexión";
      pill.className = "status-pill checking";
    }
  } catch (err) {
    pill.textContent = "Offline";
    pill.className = "status-pill checking";
  }
}

function highlightStep(stepNum) {
  for (let i = 1; i <= 3; i++) {
    const card = document.getElementById(`step${i}Card`);
    if (i < stepNum) {
      card.className = "step-card completed";
    } else if (i === stepNum) {
      card.className = "step-card active";
    } else {
      card.className = "step-card";
    }
  }
}

async function handleUploadSubmit(e) {
  e.preventDefault();
  const btn = document.getElementById("btnSubmitUpload");
  const btnText = btn.querySelector(".btn-text");
  const spinner = btn.querySelector(".spinner");

  btn.disabled = true;
  spinner.style.display = "inline-block";
  btnText.textContent = "Procesando...";

  try {
    highlightStep(1);
    logMessage("Paso 1: Preparando documento PDF para firma desatendida...", "info");

    let b64Data = DEFAULT_SAMPLE_PDF_B64;
    let filename = "documento_generado.pdf";

    if (selectedFile) {
      filename = selectedFile.name;
      b64Data = await readFileAsBase64(selectedFile);
    }

    const payload = {
      ...defaultPayload,
      subject: document.getElementById("subject").value,
      reference: document.getElementById("reference").value,
      sender: {
        userCode: document.getElementById("userCode").value,
        entityCode: "default"
      },
      addresseeLines: [
        {
          addresseeGroups: [
            {
              isOrGroup: false,
              userEntities: [
                {
                  userCode: document.getElementById("userCode").value,
                  entityCode: "default",
                  action: "SIGN"
                }
              ]
            }
          ]
        }
      ],
      documentsToSign: [
        {
          filename: filename,
          data: b64Data
        }
      ]
    };

    await sendSignaturePayload(payload);
  } catch (error) {
    logMessage(`Error en solicitud: ${error.message}`, "error");
  } finally {
    btn.disabled = false;
    spinner.style.display = "none";
    btnText.textContent = "Iniciar Firma Desatendida";
  }
}

async function handleJsonSubmit() {
  const btn = document.getElementById("btnSubmitJson");
  const btnText = btn.querySelector(".btn-text");
  const spinner = btn.querySelector(".spinner");

  let payload;
  try {
    payload = JSON.parse(document.getElementById("rawJsonInput").value);
  } catch (err) {
    alert("El JSON ingresado no es válido: " + err.message);
    return;
  }

  btn.disabled = true;
  spinner.style.display = "inline-block";
  btnText.textContent = "Enviando...";

  try {
    highlightStep(1);
    await sendSignaturePayload(payload);
  } catch (error) {
    logMessage(`Error: ${error.message}`, "error");
  } finally {
    btn.disabled = false;
    spinner.style.display = "none";
    btnText.textContent = "Enviar Payload JSON";
  }
}

async function sendSignaturePayload(payload) {
  logMessage(`Enviando POST /api/v1/documents/sign (Ref: ${payload.reference})...`, "info");
  
  const res = await fetch("/api/v1/documents/sign", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Error desconocido al procesar la firma");
  }

  logMessage(`✓ Solicitud creada con éxito! TrackingId: ${data.trackingId}`, "success");
  logMessage(`  Firma GOB IDs: PublicAccessId=${data.firmagob.publicAccessId}, DocumentId=${data.firmagob.documentId}`, "system");

  highlightStep(2);
  logMessage("Paso 2: Esperando notificación de webhook de Firma GOB...", "warning");

  await loadRequests();
}

async function loadRequests() {
  try {
    const res = await fetch("/api/v1/documents");
    if (!res.ok) return;

    const data = await res.json();
    const tbody = document.getElementById("requestsTbody");

    if (!data.items || data.items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No hay solicitudes registradas aún.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.items.map(item => {
      const isCompleted = item.status === "COMPLETED";
      const badgeClass = `badge-${item.status.toLowerCase()}`;
      
      let actionBtn = "";
      if (item.hasSignedFile) {
        actionBtn = `
          <a href="/api/v1/documents/${item.id}/download" class="btn-action-download" download>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            PDF Firmado
          </a>
        `;
      } else {
        actionBtn = `<span style="font-size:11px;color:var(--text-muted)">En proceso...</span>`;
      }

      return `
        <tr>
          <td>
            <strong>${item.reference || "Sin ref"}</strong>
            <div style="font-size:11px;color:var(--text-muted)">${item.subject || ""}</div>
          </td>
          <td>${item.originalFilename || "documento.pdf"}</td>
          <td><span class="badge ${badgeClass}">${item.status}</span></td>
          <td>
            <div class="code-tag" title="Public Access ID">${item.publicAccessId || "N/A"}</div>
            <div style="font-size:10px;color:var(--text-muted)">Doc: ${item.documentId || "N/A"}</div>
          </td>
          <td>${actionBtn}</td>
        </tr>
      `;
    }).join("");

    // Si el primer elemento está completado, actualizar el paso
    if (data.items[0] && data.items[0].status === "COMPLETED") {
      highlightStep(3);
    }
  } catch (err) {
    console.error("Error cargando solicitudes:", err);
  }
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      const base64 = result.split(",")[1] || result;
      resolve(base64);
    };
    reader.onerror = error => reject(error);
    reader.readAsDataURL(file);
  });
}
