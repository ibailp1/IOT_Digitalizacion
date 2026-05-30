const ledRoja = document.getElementById("casilla-led-roja");
const ledAmarilla = document.getElementById("casilla-led-amarilla");
const ledVerde = document.getElementById("casilla-led-verde");
const ledPuerta = document.getElementById("casilla-led-puerta");
const ledRgbEstado = document.getElementById("casilla-led-rgb");
const selectorColor = document.getElementById("selector-color");

const circuloRgb = document.querySelector(".led-rgb");
const btnActualizar = document.getElementById("btn-actualizar");
const mensajeError = document.getElementById("mensaje-error");

const btnEncenderTodo = document.getElementById("btn-encender-todo");
const btnApagarTodo = document.getElementById("btn-apagar-todo");

const todosLosInterruptores = [
  ledRoja,
  ledAmarilla,
  ledVerde,
  ledPuerta,
  ledRgbEstado
];

function obtenerCasaSeleccionada() {
  const urlParams = new URLSearchParams(window.location.search);
  const casa = urlParams.get("house");
  return casa;
}

function construirJsonEstado() {
  return {
    estado: {
      estadoLuces: {
        ledRoja: { encendida: ledRoja.checked },
        ledAmarilla: { encendida: ledAmarilla.checked },
        ledVerde: { encendida: ledVerde.checked },
        ledPuerta: { encendida: ledPuerta.checked },
        ledRgb: { 
          encendida: ledRgbEstado.checked, 
          colorRgb: selectorColor.value 
        }
      }
    }
  };
}

function enviarCambioServidor() {
  const jsonEstado = construirJsonEstado();
  const casa = obtenerCasaSeleccionada();

  // Creamos un objeto con los datos exactamente igual a como los espera tu Flask
  const datosFormulario = new URLSearchParams();
  datosFormulario.append("message", JSON.stringify(jsonEstado));
  if (casa) {
    datosFormulario.append("house", casa);
  }

  // Enviamos los datos de fondo (asíncronamente) sin molestar al navegador
  fetch("/send", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body: datosFormulario
  })
  .then(response => {
    console.log("Estado enviado a Flask con éxito (sin recargar)");
  })
  .catch(error => {
    console.error("Error al enviar el cambio:", error);
  });
}

btnActualizar.addEventListener("click", function () {
  const casa = obtenerCasaSeleccionada();
  let url = "/refresh";
  if (casa) {
    url = "/refresh?house=" + casa;
  }
  window.location.href = url;
});

btnEncenderTodo.addEventListener("click", function () {
  todosLosInterruptores.forEach(function (interr) {
    interr.checked = true;
  });
  enviarCambioServidor();
});

btnApagarTodo.addEventListener("click", function () {
  todosLosInterruptores.forEach(function (interr) {
    interr.checked = false;
  });
  enviarCambioServidor();
});

selectorColor.addEventListener("input", function (e) {
  // Actualiza el color del circulito en tiempo real
  circuloRgb.style.background = e.target.value;
});

selectorColor.addEventListener("change", function () {
  // Envía el JSON a AWS IoT SOLO cuando el usuario suelte el clic definitivo
  enviarCambioServidor();
});

todosLosInterruptores.forEach(function (interr) {
  interr.addEventListener("change", function () {
    enviarCambioServidor();
  });
});
