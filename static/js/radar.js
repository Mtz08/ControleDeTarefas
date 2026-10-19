// Radar de Demandas: comportamento mínimo, sem frameworks e sem scripts inline (CSP).
(function () {
  "use strict";

  function digitandoEmCampo(alvo) {
    return alvo.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(alvo.tagName);
  }

  // Atalhos: "n" vai para a captura rápida; "/" vai para a busca.
  document.addEventListener("keydown", function (evento) {
    if (evento.ctrlKey || evento.metaKey || evento.altKey || digitandoEmCampo(evento.target)) {
      return;
    }
    if (evento.key === "n") {
      const captura = document.getElementById("captura-titulo");
      if (captura) {
        evento.preventDefault();
        captura.focus();
      }
    } else if (evento.key === "/") {
      evento.preventDefault();
      const busca = document.getElementById("busca");
      if (busca) {
        busca.focus();
        busca.select();
      } else if (document.body.dataset.urlLista) {
        window.location.href = document.body.dataset.urlLista + "#busca";
      }
    }
  });

  // Chegando na lista por "/", já foca a busca.
  if (window.location.hash === "#busca") {
    const busca = document.getElementById("busca");
    if (busca) busca.focus();
  }

  // Evita envio duplicado (duplo clique): desabilita os botões logo após o envio.
  // O atraso zero garante que o valor do botão clicado já foi incluído no envio.
  document.addEventListener("submit", function (evento) {
    const formulario = evento.target;
    if (!formulario.matches("[data-trava-envio]")) return;
    if (formulario.dataset.enviado) {
      evento.preventDefault();
      return;
    }
    formulario.dataset.enviado = "1";
    setTimeout(function () {
      formulario.querySelectorAll("button[type=submit]").forEach(function (botao) {
        botao.disabled = true;
      });
    }, 0);
  });

  // Barras do resumo: largura vinda do servidor, aplicada via JS (a CSP proíbe style inline).
  document.querySelectorAll("[data-largura]").forEach(function (barra) {
    const largura = Math.max(0, Math.min(100, Number(barra.dataset.largura) || 0));
    barra.style.width = largura + "%";
  });

  // Botão de imprimir.
  document.querySelectorAll("[data-imprimir]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      window.print();
    });
  });

  // Formulário de demanda: mostra "aguardando quem" só quando o status pede.
  const status = document.getElementById("id_status");
  const blocosCondicionais = document.querySelectorAll("[data-mostrar-se-status]");
  function atualizarCondicionais() {
    blocosCondicionais.forEach(function (bloco) {
      const visivel = status.value === bloco.dataset.mostrarSeStatus;
      bloco.hidden = !visivel;
    });
  }
  if (status && blocosCondicionais.length) {
    status.addEventListener("change", atualizarCondicionais);
    atualizarCondicionais();
  }
})();
