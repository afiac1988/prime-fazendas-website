/* Prime Fazendas — comportamento do site. Sem bibliotecas, sem dependências. */
(function () {
  'use strict';

  /* ---------------------------------------------------- menu mobile ---- */
  var botao = document.querySelector('.hamburguer');
  var nav = document.getElementById('nav-principal');

  if (botao && nav) {
    botao.addEventListener('click', function () {
      var aberto = botao.getAttribute('aria-expanded') === 'true';
      botao.setAttribute('aria-expanded', String(!aberto));
      nav.setAttribute('data-aberto', String(!aberto));
    });

    nav.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') {
        botao.setAttribute('aria-expanded', 'false');
        nav.setAttribute('data-aberto', 'false');
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && botao.getAttribute('aria-expanded') === 'true') {
        botao.setAttribute('aria-expanded', 'false');
        nav.setAttribute('data-aberto', 'false');
        botao.focus();
      }
    });
  }

  /* ------------------------------------------------ filtro de imóveis ---- */
  var filtros = document.querySelectorAll('.filtro[data-filtro]');
  var cards = document.querySelectorAll('.imovel[data-tipo]');
  var contador = document.getElementById('contador-imoveis');

  if (filtros.length && cards.length) {
    filtros.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var alvo = btn.getAttribute('data-filtro');
        var visiveis = 0;

        filtros.forEach(function (b) {
          b.setAttribute('aria-pressed', String(b === btn));
        });

        cards.forEach(function (card) {
          var mostra = alvo === 'todos' || card.getAttribute('data-tipo') === alvo;
          card.hidden = !mostra;
          if (mostra) visiveis++;
        });

        if (contador) {
          contador.textContent = visiveis + (visiveis === 1 ? ' propriedade' : ' propriedades');
        }
      });
    });
  }

  /* ------------------------------------------- formulário via WhatsApp --- */
  var form = document.querySelector('form[data-modo="whatsapp"]');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var numero = form.getAttribute('data-whatsapp') || '';
      if (!numero) {
        alertaForm(form, 'O número de WhatsApp ainda não foi configurado. Use o e-mail de contato.');
        return;
      }

      var dados = new FormData(form);
      var linhas = ['*Contato pelo site — Prime Fazendas*', ''];
      var rotulos = {
        nome: 'Nome',
        email: 'E-mail',
        telefone: 'Telefone',
        interesse: 'Interesse',
        regiao: 'Região',
        investimento: 'Faixa de investimento',
        mensagem: 'Mensagem'
      };

      Object.keys(rotulos).forEach(function (chave) {
        var v = (dados.get(chave) || '').toString().trim();
        if (v) linhas.push(rotulos[chave] + ': ' + v);
      });

      var url = 'https://wa.me/' + numero + '?text=' + encodeURIComponent(linhas.join('\n'));
      window.open(url, '_blank', 'noopener');
      alertaForm(form, 'Abrimos o WhatsApp com a sua mensagem pronta. Se não abriu, verifique o bloqueador de pop-ups.');
    });
  }

  function alertaForm(f, texto) {
    var box = f.querySelector('[data-retorno]');
    if (!box) return;
    box.textContent = texto;
    box.hidden = false;
  }

  /* ------------------------------------------------- ano no rodapé ---- */
  var ano = document.querySelectorAll('[data-ano]');
  ano.forEach(function (el) { el.textContent = new Date().getFullYear(); });
})();
