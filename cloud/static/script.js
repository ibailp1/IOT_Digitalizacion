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

  const formulario = document.createElement("form");
  formulario.method = "POST";
  formulario.action = "/send";

  const inputMessage = document.createElement("input");
  inputMessage.type = "hidden";
  inputMessage.name = "message";
  inputMessage.value = JSON.stringify(jsonEstado);
  formulario.appendChild(inputMessage);

  if (casa) {
    const inputHouse = document.createElement("input");
    inputHouse.type = "hidden";
    inputHouse.name = "house";
    inputHouse.value = casa;
    formulario.appendChild(inputHouse);
  }

  document.body.appendChild(formulario);
  formulario.submit();
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

selectorColor.addEventListener("change", function (e) {
  circuloRgb.style.background = e.target.value;
  enviarCambioServidor();
});

todosLosInterruptores.forEach(function (interr) {
  interr.addEventListener("change", function () {
    enviarCambioServidor();
  });
});
