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

function actualizarEstadoLuces(datos) {
  
  casillaLedRoja.checked = datos["estado-luces"]["led-roja"].encendida;
  casillaLedAmarilla.checked = datos["estado-luces"]["led-amarilla"].encendida;
  casillaLedVerde.checked = datos["estado-luces"]["led-verde"].encendida;
  casillaLedPuerta.checked = datos["estado-luces"]["led-puerta"].encendida;
  casillaLedRgb.checked = datos["estado-luces"]["led-rgb"].encendida;
  
  selectorColorRgb.value = datos["estado-luces"]["led-puerta"].color;
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
    console.info("Error al enviar el comando.");
    console.info(payload);
    console.error(error);
  });
}

function solicitarEstadoLuces() {
  fetch("/solicitar-estado-luces")
    .then(function (respuesta) {
      return respuesta.json();
    })
    .then(function (respuesta) {
      console.log(respuesta);
      const datos = respuesta.data;
      if (datos) actualizarEstadoLuces(datos);
    })
    .catch(function (error) {
      console.info("Error al solicitar el estado de las luces.");
      console.error(error);
    });
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

(async function cargarDatos() {
    const response = await fetch('/obtener-telemetria-durante-las-ultimas-24-horas');
    const data = await response.json();

    const timestamps = data.map(item => item.timestamp);
    const temperaturas = data.map(item => item.temperatura);
    const humedades = data.map(item => item.humedad);
    const distancias = data.map(item => item.distancia);

    const ctx = document.getElementById('myChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: timestamps,
            datasets: [
                {
                    label: 'Temperatura (°C)',
                    data: temperaturas,
                    borderColor: 'rgb(255, 99, 132)',
                    fill: false
                },
                {
                    label: 'Humedad (%)',
                    data: humedades,
                    borderColor: 'rgb(54, 162, 235)',
                    fill: false
                },
                {
                    label: 'Distancia (cm)',
                    data: distancias,
                    borderColor: 'rgb(75, 192, 192)',
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
})();
