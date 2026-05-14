<?php
/**
 * PluginEternityTab — aba "Eternity SecOps" em Ticket, Computer, Problem, Change.
 */
class PluginEternityTab extends CommonGLPI {

    static function getTypeName($nb = 0) {
        return 'Eternity SecOps';
    }

    function getTabNameForItem(CommonGLPI $item, $withtemplate = 0) {
        $supported = ['Ticket', 'Computer', 'Problem', 'Change'];
        if (in_array($item->getType(), $supported)) {
            return self::createTabEntry('Eternity SecOps', 0, $item->getType());
        }
        return '';
    }

    static function displayTabContentForItem(CommonGLPI $item, $tabnum = 1, $withtemplate = 0) {
        global $CFG_GLPI;

        $config   = PluginEternityConfig::getInstance();
        $apiBase  = rtrim($config->fields['api_url'] ?? '', '/');
        $apiKey   = $config->fields['api_key'] ?? '';

        if (empty($apiBase) || empty($apiKey)) {
            echo '<div class="alert alert-warning m-3">';
            echo '<strong>Eternity SecOps</strong>: configure a URL e API Key em <em>Configuração &rarr; Plugins &rarr; Eternity SecOps</em>.';
            echo '</div>';
            return true;
        }

        $objectType = $item->getType();
        $objectId   = $item->getID();

        // Solicitar token de widget via API do Eternity
        $tokenUrl = $apiBase . '/glpi-widget/token';
        $payload  = json_encode([
            'object_type' => $objectType,
            'object_id'   => $objectId,
        ]);

        $ch = curl_init($tokenUrl);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 10,
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $payload,
            CURLOPT_HTTPHEADER     => [
                'Content-Type: application/json',
                'Authorization: Bearer ' . $apiKey,
            ],
            CURLOPT_SSL_VERIFYPEER => (bool)($config->fields['verify_ssl'] ?? true),
        ]);
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($httpCode !== 200 && $httpCode !== 201) {
            echo '<div class="alert alert-danger m-3">Eternity SecOps: erro ao obter token de widget (HTTP ' . $httpCode . ').</div>';
            return true;
        }

        $data      = json_decode($response, true);
        $widgetUrl = $data['widget_url'] ?? '';

        if (empty($widgetUrl)) {
            echo '<div class="alert alert-danger m-3">Eternity SecOps: URL do widget não retornada.</div>';
            return true;
        }

        $iframeId = 'eternity-widget-' . $objectType . '-' . $objectId;
        echo '<div class="p-2">';
        echo '<iframe id="' . htmlspecialchars($iframeId) . '" src="' . htmlspecialchars($widgetUrl) . '" ';
        echo 'style="width:100%;min-height:380px;border:none;border-radius:8px;background:#f9fafb;" ';
        echo 'title="Eternity SecOps"></iframe>';
        echo '</div>';

        return true;
    }
}
