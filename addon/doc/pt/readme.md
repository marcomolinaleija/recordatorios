# Recordatorios

Este complemento permite ao usuário adicionar lembretes de forma simples, notificando com um som do NVDA ou um som personalizado quando a hora programada chegar.

## Uso do complemento

O complemento inclui 3 gestos não atribuídos nos gestos de entrada do NVDA, sob a categoria "Lembretes":

### 1. Abrir a janela para adicionar um lembrete

Esta opção permitirá que você adicione um ou mais lembretes. Ao abrir a janela, você será automaticamente focado na caixa para digitar a mensagem do lembrete.

- **Configuração do lembrete**:
  - Após digitar sua mensagem, você encontrará duas caixas combinadas. A primeira permitirá selecionar a hora no formato de 24 horas, e a segunda, os minutos. Você pode modificar esses valores conforme suas necessidades.
  - Também há 2 caixas de seleção, que estão desmarcadas por padrão. A primeira pergunta se o lembrete será recorrente. Quando marcada, aparecerá uma caixa combinada onde você poderá selecionar a frequência: diária, semanal, mensal ou personalizada.
  - A segunda caixa, também desmarcada por padrão, pergunta se você deseja adicionar um som personalizado para o lembrete. Quando marcada, aparecerão mais opções.

- **Sons personalizados**:
  - A primeira opção será uma caixa combinada que carregará os sons da pasta que você selecionou. Apenas arquivos com a extensão .wav serão carregados.
  - A segunda opção é um botão para reproduzir o som selecionado na caixa anterior, permitindo uma pré-escuta antes de confirmar sua escolha.
  - Por fim, você encontrará um botão para selecionar a pasta de sons, permitindo carregar os sons disponíveis na caixa de seleção.

Depois de configurar todos os elementos de acordo com suas preferências, basta pressionar o botão "Adicionar lembrete" para salvá-lo. Os lembretes são armazenados em um arquivo chamado "lembretes.json" na pasta do usuário do NVDA. Além disso, um arquivo adicional chamado "sons_lembretes.json" é gerado, facilitando o carregamento da pasta de sons selecionada. Isso significa que, após reiniciar o NVDA ou desligar e ligar o PC novamente, a pasta de sons estará disponível para que você escolha um som personalizado para o seu lembrete sem precisar selecionar a pasta novamente.

### 2. Verificar lembretes ativos

Esta opção permite que você revise os lembretes que configurou. Ao selecionar esta opção, uma janela explorável será aberta onde você poderá navegar com as setas para revisar os lembretes junto com a hora programada.

### 3. Abrir o diálogo para excluir lembretes

Isso abrirá um diálogo de seleção para que você possa excluir um lembrete.

## Menu de ferramentas do NVDA

Após instalar corretamente o complemento, também será adicionado um menu na seção de ferramentas com as seguintes opções:

- Adicionar lembrete
- Ver lembretes ativos
- Excluir lembrete

A única opção que muda aqui é a de "Excluir lembrete". Ao selecionar essa opção, se você tiver lembretes configurados, aparecerá uma lista com seus nomes para que você possa excluir um. Se você não tiver lembretes ativos, aparecerá uma mensagem informando que não foram encontrados lembretes configurados.

## Configurações do complemento

No menu de Preferências > Opções do NVDA, será criada uma nova categoria chamada "Configuração de Lembretes". Esta categoria contém as seguintes opções:

- **Número de notificações**: A primeira caixa pedirá que você selecione o número de notificações que serão enviadas para o lembrete.

- **Intervalo das notificações**: A segunda caixa pedirá que você defina o intervalo entre as notificações. Por exemplo, se você selecionou 2 vezes na caixa anterior, esse intervalo determinará quantos segundos entre essas notificações, podendo escolher intervalos de 5, 10 ou 20 segundos.

# Sugestões

Se você desejar fazer alguma sugestão para o complemento, pode enviar um e-mail para o seguinte endereço:

[email](mailto:marcomolinaleija@hotmail.com)

# Histórico de versões

- **Versão 1.1**: Adicionada a possibilidade de personalizar a recorrência dos lembretes (Em minutos).

- **Versão 1.0**: Versão inicial do complemento, contendo todas as opções descritas acima.

---

E isso é tudo por enquanto. Muito obrigado por baixar, instalar e testar este complemento.