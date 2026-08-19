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
  var filtroAtivo = 'todos';

  function aplicarFiltro() {
    var visiveis = 0;
    cards.forEach(function (card) {
      var mostra = filtroAtivo === 'todos' || card.getAttribute('data-tipo') === filtroAtivo;
      card.hidden = !mostra;
      if (mostra) visiveis++;
    });
    if (contador) {
      contador.textContent = visiveis + (visiveis === 1 ? ' propriedade' : ' propriedades');
    }
  }

  if (filtros.length && cards.length) {
    filtros.forEach(function (btn) {
      btn.addEventListener('click', function () {
        filtroAtivo = btn.getAttribute('data-filtro');
        filtros.forEach(function (b) {
          b.setAttribute('aria-pressed', String(b === btn));
        });
        aplicarFiltro();
      });
    });
  }

  /* -------------------------------------------------- ordenar imóveis ---- */
  var grade = document.getElementById('grade-imoveis');
  var selectOrdenar = document.getElementById('ordenar-imoveis');

  if (grade && selectOrdenar) {
    var ordemOriginal = Array.prototype.slice.call(grade.children);

    selectOrdenar.addEventListener('change', function () {
      var modo = selectOrdenar.value;
      var itens;

      if (modo === 'recentes') {
        itens = ordemOriginal.slice();
      } else {
        var campo = modo.indexOf('preco') === 0 ? 'preco' : 'area';
        var direcao = modo.indexOf('desc') !== -1 ? -1 : 1;
        itens = Array.prototype.slice.call(grade.children).sort(function (a, b) {
          var va = parseFloat(a.getAttribute('data-' + campo)) || 0;
          var vb = parseFloat(b.getAttribute('data-' + campo)) || 0;
          return (va - vb) * direcao;
        });
      }

      itens.forEach(function (item) { grade.appendChild(item); });
      /* a filtragem por tipo continua valendo após reordenar, pois só usa "hidden" */
      aplicarFiltro();
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
    var modalAnterior = modal.querySelector('.foto-modal__anterior');
    var modalProximo = modal.querySelector('.foto-modal__proximo');
    var fotosAtuais = [];
    var indiceAtual = -1;
    var focoAnterior = null;

    function coletarFotos(link) {
      var container = (link.closest && (link.closest('.galeria') || link.closest('.grade-imoveis'))) || document;
      return Array.prototype.slice.call(container.querySelectorAll('.js-foto-modal'));
    }

    function mostrarFoto(indice) {
      if (!fotosAtuais.length || !modalImg) return;
      indiceAtual = (indice + fotosAtuais.length) % fotosAtuais.length;
      var link = fotosAtuais[indiceAtual];
      var src = link.getAttribute('data-foto-modal-src') || link.getAttribute('href');
      var alt = link.getAttribute('data-foto-modal-alt') || (link.querySelector('img') && link.querySelector('img').alt) || '';
      modalImg.src = src;
      modalImg.alt = alt;
      if (modalLegenda) {
        modalLegenda.textContent = alt;
      }
      var temVarias = fotosAtuais.length > 1;
      if (modalAnterior) modalAnterior.hidden = !temVarias;
      if (modalProximo) modalProximo.hidden = !temVarias;
    }

    function abrirModal(link) {
      fotosAtuais = coletarFotos(link);
      var indice = fotosAtuais.indexOf(link);
      focoAnterior = document.activeElement;
      mostrarFoto(indice === -1 ? 0 : indice);
      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('modal-aberta');
      if (modalFechar) modalFechar.focus();
    }

    function fecharModal() {
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('modal-aberta');
      if (modalImg) {
        modalImg.src = '';
        modalImg.alt = '';
      }
      if (modalLegenda) {
        modalLegenda.textContent = '';
      }
      fotosAtuais = [];
      indiceAtual = -1;
      if (focoAnterior && typeof focoAnterior.focus === 'function') {
        focoAnterior.focus();
      }
    }

    function elementosFocaveis() {
      return [modalFechar, modalAnterior, modalProximo].filter(function (el) {
        return el && !el.hidden;
      });
    }

    document.addEventListener('click', function (e) {
      var link = e.target.closest && e.target.closest('.js-foto-modal');
      if (link) {
        e.preventDefault();
        abrirModal(link);
        return;
      }

      if (modal.hidden) return;

      if (e.target.closest && e.target.closest('.foto-modal__anterior')) {
        mostrarFoto(indiceAtual - 1);
        return;
      }
      if (e.target.closest && e.target.closest('.foto-modal__proximo')) {
        mostrarFoto(indiceAtual + 1);
        return;
      }
      if (e.target === modal || e.target === modalJanela || (e.target.closest && e.target.closest('.foto-modal__fechar'))) {
        fecharModal();
      }
    });

    document.addEventListener('keydown', function (e) {
      if (modal.hidden) return;

      if (e.key === 'Escape') {
        fecharModal();
        return;
      }
      if (e.key === 'ArrowLeft') {
        mostrarFoto(indiceAtual - 1);
        return;
      }
      if (e.key === 'ArrowRight') {
        mostrarFoto(indiceAtual + 1);
        return;
      }
      if (e.key === 'Tab') {
        var focaveis = elementosFocaveis();
        if (!focaveis.length) return;
        var primeiro = focaveis[0];
        var ultimo = focaveis[focaveis.length - 1];

        if (e.shiftKey && document.activeElement === primeiro) {
          e.preventDefault();
          ultimo.focus();
        } else if (!e.shiftKey && document.activeElement === ultimo) {
          e.preventDefault();
          primeiro.focus();
        } else if (focaveis.indexOf(document.activeElement) === -1) {
          e.preventDefault();
          primeiro.focus();
        }
      }
    });
  }

  /* ------------------------------------------------- ano no rodapé ---- */
  var ano = document.querySelectorAll('[data-ano]');
  ano.forEach(function (el) { el.textContent = new Date().getFullYear(); });
})();
