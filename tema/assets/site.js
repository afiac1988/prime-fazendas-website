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

  /* ------------------------------------------- visualizador de imagens --- */
  var modal = document.querySelector('.foto-modal');
  if (modal) {
    var modalJanela = modal.querySelector('.foto-modal__janela');
    var modalImg = modal.querySelector('.foto-modal__img');
    var modalLegenda = modal.querySelector('.foto-modal__legenda');
    var modalFechar = modal.querySelector('.foto-modal__fechar');

    function abrirModal(src, alt) {
      if (!src || !modalImg) return;
      modalImg.src = src;
      modalImg.alt = alt || '';
      if (modalLegenda) {
        modalLegenda.textContent = alt || '';
      }
      modal.hidden = false;
      document.body.classList.add('modal-aberta');
      if (modalFechar) modalFechar.focus();
    }

    function fecharModal() {
      modal.hidden = true;
      document.body.classList.remove('modal-aberta');
      if (modalImg) {
        modalImg.src = '';
        modalImg.alt = '';
      }
      if (modalLegenda) {
        modalLegenda.textContent = '';
      }
    }

    document.addEventListener('click', function (e) {
      var link = e.target.closest && e.target.closest('.js-foto-modal');
      if (link) {
        var src = link.getAttribute('data-foto-modal-src') || link.getAttribute('href');
        var alt = link.getAttribute('data-foto-modal-alt') || (link.querySelector('img') && link.querySelector('img').alt) || '';
        e.preventDefault();
        abrirModal(src, alt);
        return;
      }

      if (e.target === modal || e.target === modalJanela || (e.target.closest && e.target.closest('.foto-modal__fechar'))) {
        if (!modal.hidden) fecharModal();
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !modal.hidden) {
        fecharModal();
      }
    });
  }

  /* ------------------------------------------------- ano no rodapé ---- */
  var ano = document.querySelectorAll('[data-ano]');
  ano.forEach(function (el) { el.textContent = new Date().getFullYear(); });
})();
