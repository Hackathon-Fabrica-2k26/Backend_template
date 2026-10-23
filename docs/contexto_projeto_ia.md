# CONTEXTO DE PROJETO: COPILOTO PEDAGÓGICO "DO ZERO À AUTONOMIA COM IA"
> **Instrução para a IA:** Você está atuando como Arquiteto de Software, Especialista em IA Generativa e Mentor de Hackathon neste projeto. Utilize as diretrizes, restrições e arquitetura abaixo para responder a quaisquer solicitações de código, design de produto, prompts de LLM e documentação técnica.

---

## 1. Identificação e Metadados do Evento
- **Evento:** Hackathon Fábrica de Software 2026 (IFC Campus Araquari).
- **Desafio Oficial:** *"Do Zero à Autonomia: 24H com IA"*.
- **Tema Central:** Como ajudar pessoas comuns a descobrir e aproveitar o potencial da IA, avançando do primeiro contato para um uso mais consciente, útil e autônomo em suas atividades reais.
- **Prazo de Desenvolvimento:** 24 horas (foco em MVP de altíssimo impacto visual e funcional, sem complexidade desnecessária).

---

## 2. O Problema Real
Professores dos anos iniciais do Ensino Fundamental (crianças de 5 a 9 anos) enfrentam salas de aula com 25 a 35 alunos, onde a diversidade de ritmos de aprendizagem, dificuldades de atenção, desregulação sensorial e possíveis traços de neurodivergência (como TDAH e TEA) tornam o ensino individualizado quase impossível.

### A barreira no uso de IA pelo professor comum:
1. **Falta de repertório para prompts:** Tentam usar ferramentas como ChatGPT com perguntas rasas (*"como ajudar aluno que não para quieto?"*) e recebem conselhos genéricos, teóricos e pouco práticos.
2. **Desconhecimento sobre contexto:** Não sabem quais dados pedagógicos e comportamentais são relevantes para fornecer à IA a fim de obter planos adaptados de qualidade.
3. **Riscos de Privacidade e LGPD:** Não sabem como proteger os dados sensíveis dos alunos (dados de menores protegidos pelo Art. 14 da LGPD).
4. **Falta de julgamento crítico:** Tendem a aceitar cegamente as respostas ou rejeitar a ferramenta por desconfiança.

---

## 3. A Solução Proposta: "Marsupi"
Uma plataforma e aplicativo que **conduz o professor do zero ao uso autônomo de IA**, capacitando-o a mapear perfis de aprendizagem e criar atividades adaptadas para a sua turma.

### O Fluxo da Solução (Jornada "Zero à Autonomia"):
1. **Entrada Guiada (Sem jargões):** O professor responde a perguntas pedagógicas simples e objetivas sobre a rotina da criança (ex: foco em tarefas longas, interação social, coordenação motora, interesses de hiperfoco como dinossauros ou carros).
2. **Filtro de Privacidade Ativo (Educação em LGPD):** O aplicativo demonstra visualmente ao professor como anonimizar os dados (ex: substitui nome real por codinome pedagógico como *"Aluno Alfa"*, remove cidade, idade exata em datas) e ensina o porquê dessa prática.
3. **Radar de Habilidades & Desafios:** A IA processa o contexto e gera um mapeamento visual dos **Pontos Fortes** (alavancas de aprendizagem) e **Áreas de Suporte** (desafios comportamentais ou cognitivos), estilo dashboard gamificado.
4. **Plano de Atividades Adaptadas (Micro-PEI):** Geração de 3 a 5 dinâmicas práticas e inclusivas para aplicar em sala de aula nas semanas seguintes, alavancando os pontos fortes da criança para trabalhar suas dificuldades.
5. **Ciclo de Refinamento e Pensamento Crítico:** O app provoca o professor a avaliar: *"Essa atividade é viável na sua sala com 30 alunos? O que você gostaria de adaptar?"*, ensinando o professor a refinar a solicitação para a IA com autonomia.

---

## 4. Diretrizes Éticas e Limites Rígidos (IMPORTANTÍSSIMO)
- 🚫 **NÃO é uma ferramenta de diagnóstico médico ou psicológico:** O sistema NUNCA deve emitir laudos como *"probabilidade de 80% de autismo/TDAH"*. Em vez disso, categoriza **necessidades pedagógicas e comportamentais** (ex: *"alta necessidade de suporte visual"*, *"busca de estímulo motor frequente"*).
- 🛡️ **Aviso Ético Obrigatório:** Todas as saídas contêm disclaimer claro: *"Este relatório tem finalidade estritamente pedagógica. Sinais atípicos persistentes devem ser encaminhados à coordenação pedagógica e profissionais de saúde."*
- 🔒 **Zero Exposição de Menores:** Nenhum dado pessoal identificável (PII) é enviado para APIs externas de LLM. Dados de aluno/responsável nunca vão para a LLM.

---

## 5. Stack Tecnológica e Decisões Arquiteturais
- **Backend:** Python 3.11+ / Django 5 + Django REST Framework (DRF), integração com LLM via API (Google Gemini 1.5/2.0 Flash ou OpenAI GPT-4o-mini).
  - **Professor:** próprio `User` (campos `ano`, `escola`, `matricula`), sem model `Professor`.
  - **3 apps de domínio:**
    - `escolas`: `Config`, `Escola`, `Turma` (com M2M `professores`).
    - `alunos`: `Aluno`, `Responsavel`, `MetaDados` (com `perfil_disc` D/I/S/C — não é diagnóstico).
    - `pedagogico`: `Atividade`, `Relatorio` (com `dados` JSON).
  - **Segurança de chave:** `Config.api_key` fica armazenada no banco, mas é `write_only` na API.
  - **Autenticação / Login:** matrícula + senha + OTP de 4 dígitos por e-mail (SEM login com Google).
  - **Privacidade:** dados de aluno/responsável nunca vão para a LLM.
  - **Rotas do Backend:** apps usam `SimpleRouter` e cada lista entra em `api_root` (`config/urls.py`).
- **Frontend Web:** Vue 3 + Vuetify 4 + Vite + TypeScript.
- **Frontend Mobile (Flutter):** a confirmar.
- **Design (Figma):** https://www.figma.com/design/EDj1MQgpyqyqD7xa9u9PHv/HACKATHON
  - **Cores:** `primary #356b5b`, `text #263d35`, `background #f7f7f1`, `support #a9c7b4`.
  - **Fonte:** `Poppins`.

---

## 6. Estrutura de Dados e Contrato de API (Exemplo)

### Payload de Entrada do Professor (Contexto Guiado):
```json
{
  "student_pseudonym": "Aluno A",
  "age_group": "6-7 anos",
  "strengths_observed": ["Excelente memória visual", "Interesse profundo por astronomia", "Gosta de ajudar colegas"],
  "challenges_observed": ["Dificuldade de permanecer sentado mais de 10 min", "Sensibilidade a ruídos altos", "Frustração ao errar caligrafia"],
  "classroom_context": "Turma de 26 alunos, aula de 4 horas diárias"
}
```

### Formato de Resposta Esperado da LLM (JSON Estruturado):
```json
{
  "profile_summary": "Perfil com alto raciocínio visual e forte motivação por temáticas exploratórias, necessitando de suporte para autorregulação motora e previsibilidade sensorial.",
  "radar_metrics": {
    "foco_sustentado": 40,
    "raciocinio_visual": 90,
    "interacao_social": 80,
    "regulacao_sensorial": 50,
    "coordenacao_fina": 60
  },
  "strengths": [
    "Memória fotográfica e facilidade para associar símbolos visuais",
    "Empatia e disposição para dinâmicas colaborativas"
  ],
  "support_needs": [
    "Pausas ativas a cada 10 a 15 minutos para regulação física",
    "Uso de pistas visuais de rotina para diminuir ansiedade"
  ],
  "adapted_activities": [
    {
      "title": "Missão Espacial: Caligrafia nas Estrelas",
      "objective": "Trabalhar coordenação motora usando o hiperfoco em planetas",
      "duration": "15 minutos",
      "instructions": "O aluno traça constelações em folhas com guias pontilhadas antes da escrita formal.",
      "inclusive_tip": "Permitir que a turma inteira faça a 'missão', integrando a criança sem estigmatizá-la."
    }
  ],
  "autonomy_coaching_tip": "Professor, você notou se o aluno reage melhor quando o comando é falado ou quando há um desenho no quadro? Experimente pedir à IA: 'Como adaptar a instrução de matemática usando ícones visuais?'"
}
```

---

## 7. Como as IAs devem responder ao trabalhar neste projeto:
1. Priorizar código limpo, executável e pronto para o MVP de 24 horas.
2. Evitar dependências pesadas ou configurações complexas.
3. Manter o vocabulário em **Português (pt-BR)**.
4. Lembrar sempre que o protagonista do produto é a **autonomia do professor**, ensinando-o a pensar criticamente ao usar inteligência artificial.
