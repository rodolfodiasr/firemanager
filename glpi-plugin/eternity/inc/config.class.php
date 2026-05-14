<?php
/**
 * PluginEternityConfig — configuração do plugin (URL + API Key).
 */
class PluginEternityConfig extends CommonDBTM {

    static $rightname = 'config';

    static function getInstance() {
        $config = new self();
        $config->getFromDB(1);
        if (!$config->fields) {
            $config->fields = ['id' => 1, 'api_url' => '', 'api_key' => '', 'verify_ssl' => 1];
        }
        return $config;
    }

    static function getTypeName($nb = 0) {
        return 'Configuração Eternity SecOps';
    }

    function showForm($ID, array $options = []) {
        $config = self::getInstance();
        echo '<form method="POST" action="' . Toolbox::getItemTypeFormURL('PluginEternityConfig') . '">';
        echo '<div class="card mb-4">';
        echo '<div class="card-header"><h3>Eternity SecOps — Configuração</h3></div>';
        echo '<div class="card-body">';
        echo '<div class="mb-3"><label>URL da API Eternity SecOps</label>';
        echo '<input type="url" name="api_url" class="form-control" value="' . htmlspecialchars($config->fields['api_url']) . '" placeholder="https://eternity.seudominio.com"/></div>';
        echo '<div class="mb-3"><label>API Key (Bearer token)</label>';
        echo '<input type="password" name="api_key" class="form-control" value="' . htmlspecialchars($config->fields['api_key']) . '"/></div>';
        echo '<div class="mb-3 form-check"><input type="checkbox" class="form-check-input" name="verify_ssl" id="verify_ssl" ' . ($config->fields['verify_ssl'] ? 'checked' : '') . '/>';
        echo '<label class="form-check-label" for="verify_ssl">Verificar certificado SSL</label></div>';
        echo '</div><div class="card-footer">';
        echo Html::submit('Salvar', ['name' => 'update', 'class' => 'btn btn-primary']);
        echo '</div></div>';
        Html::closeForm();
    }

    function prepareInputForAdd($input) { return $this->prepareInput($input); }
    function prepareInputForUpdate($input) { return $this->prepareInput($input); }

    private function prepareInput($input) {
        $input['verify_ssl'] = isset($input['verify_ssl']) ? 1 : 0;
        return $input;
    }
}
