const casillaLedRoja = document.getElementById("casilla-led-roja");
const casillaLedAmarilla = document.getElementById("casilla-led-amarilla");
const casillaLedVerde = document.getElementById("casilla-led-verde");
const casillaLedPuerta = document.getElementById("casilla-led-puerta");
const casillaLedRgb = document.getElementById("casilla-led-rgb");
const selectorColorRgb = document.getElementById("selector-color-rgb");

const circulitoRgb = document.querySelector(".circulito-led-rgb");
const btnActualizar = document.getElementById("btn-actualizar");
const mensajeError = document.getElementById("mensaje-error");

const btnEncenderTodo = document.getElementById("btn-encender-todo");
const btnApagarTodo = document.getElementById("btn-apagar-todo");

const todosLosInterruptores = [
  casillaLedRoja,
  casillaLedAmarilla,
  casillaLedVerde,
  casillaLedPuerta,
  casillaLedRgb
];

function actualizarEstadoLuces(data) {
  
  casillaLedRoja.checked = data["estado-luces"]["led-roja"].encendida;
  casillaLedAmarilla.checked = data["estado-luces"]["led-amarilla"].encendida;
  casillaLedVerde.checked = data["estado-luces"]["led-verde"].encendida;
  casillaLedPuerta.checked = data["estado-luces"]["led-puerta"].encendida;
  casillaLedRgb.checked = data["estado-luces"]["led-rgb"].encendida;
  selectorColorRgb.value = data["estado-luces"]["led-puerta"].color;
  
  circulitoRgb.style.background = selectorColorRgb.value;
}

function enviarComandoLuces(cuerpo_mensaje) {

  const cabeza_mensaje = {
    "codigo-mensaje": "comando-luces"
  };

  const payload = {
    "cabeza-mensaje": cabeza_mensaje,
    "cuerpo-mensaje": cuerpo_mensaje
  };

  fetch("/enviar-comando", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  })
  .then(function (response) {
    console.info("Comando enviado.");
    console.info(payload);
  })
  .catch(function (error) {
    console.error("Error al enviar comando.");
    console.info(payload);
  });
}

function solicitarEstadoLuces() {
  fetch("/solicitar-estado-luces")
    .then(function (response) { return response.json(); })
    .then(function (data) {
      actualizarEstadoLuces(data);
    })
    .catch(function (Error) {});
}

function procesarTelemetria(data) {
  console.error("NO IMPLEMENTADO");
}

async function esperarTelemetria() {
    const response = await fetch("/esperar-telemetria");
    const data = await response.json();
    return data;
}

window.onload = function() {
    solicitarEstadoLuces();
};

btnActualizar.addEventListener("click", function () {
  solicitarEstadoLuces();
});

btnEncenderTodo.addEventListener("click", function () {
  todosLosInterruptores.forEach(function (interruptor) {
    interruptor.checked = true;
    const cuerpo_mensaje = {};
    cuerpo_mensaje[interruptor.dataset["nombreLuz"]] = {
      "encendida": interruptor.checked
    };
    enviarComandoLuces(cuerpo_mensaje);
  });
});

btnApagarTodo.addEventListener("click", function () {
  todosLosInterruptores.forEach(function (interruptor) {
    interruptor.checked = false;
    const cuerpo_mensaje = {};
    cuerpo_mensaje[interruptor.dataset["nombreLuz"]] = {
      "encendida": interruptor.checked
    };
    enviarComandoLuces(cuerpo_mensaje);
  });
});

selectorColorRgb.addEventListener("input", function (argumentos_evento) {
  // Actualiza el color del circulito en tiempo real
  const interruptor = argumentos_evento.target;
  circulitoRgb.style.background = interruptor.value;
});

selectorColorRgb.addEventListener("change", function (argumentos_evento) {
  // Envía el JSON a AWS IoT SOLO cuando el usuario suelte el clic definitivo
  const interruptor = argumentos_evento.target;
  const cuerpo_mensaje = {};
  cuerpo_mensaje[interruptor.dataset["nombreLuz"]] = {
    "color": interruptor.value
  };
  enviarComandoLuces(cuerpo_mensaje);
});

todosLosInterruptores.forEach(function (interruptor) {
  interruptor.addEventListener("change", function () {
    const cuerpo_mensaje = {};
    cuerpo_mensaje[interruptor.dataset["nombreLuz"]] = {
      "encendida": interruptor.checked
    };
    enviarComandoLuces(cuerpo_mensaje);
  });
});
