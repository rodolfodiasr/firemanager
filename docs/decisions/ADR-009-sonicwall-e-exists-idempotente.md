# ADR-009 — SonicWall: E_EXISTS deve ser tratado como sucesso idempotente

## Contexto

Ao tentar criar uma regra de acesso (ou objeto de endereço/serviço) que já existe no SonicWall, a API retorna HTTP 4xx com `info[].code == "E_EXISTS"`. O comportamento anterior do conector era tratar qualquer resposta não-200/201 como falha, fazendo a operação ficar com `status = failed` e exibindo JSON bruto no frontend.

O estado desejado já estava atingido — a regra existe. Falhar é incorreto.

## Decisão

Em `create_rule()` (e por extensão qualquer método de criação), após receber resposta de erro HTTP:

1. Parsear o JSON da resposta
2. Buscar `body["status"]["info"]` (o array `info` está **dentro** de `body["status"]`, não na raiz)
3. Se qualquer entrada tiver `code == "E_EXISTS"`: retornar `ExecutionResult(success=True, already_existed=True)`
4. O campo `already_existed` é propagado para `action_plan` e detectado pelo frontend para exibir mensagem amigável

## NÃO faça

- ❌ Buscar `body["info"]` diretamente — o SonicWall encapsula dentro de `body["status"]["info"]`
- ❌ Tratar E_EXISTS como warning silencioso sem informar o usuário — mostrar a tabela com detalhes da regra existente

## Consequências

- Operações idempotentes: criar a mesma regra duas vezes é seguro
- Frontend exibe: "Regra já existia no dispositivo — nenhuma alteração necessária:" + tabela
- Aplicar o mesmo padrão em `create_nat_policy` e `create_route_policy` quando necessário
