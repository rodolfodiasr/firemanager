<?php
/**
 * Eternity SecOps — GLPI Plugin
 * Adiciona aba "Eternity SecOps" em Tickets e Computadores.
 */

define('PLUGIN_ETERNITY_VERSION', '1.0.0');
define('PLUGIN_ETERNITY_MIN_GLPI', '10.0.0');

function plugin_init_eternity() {
    global $PLUGIN_HOOKS;

    $PLUGIN_HOOKS['csrf_compliant']['eternity'] = true;
    $PLUGIN_HOOKS['item_get_events']['eternity'] = ['PluginEternityTab' => ['Ticket', 'Computer', 'Problem', 'Change']];

    if (!isset($_SESSION['glpiactiveprofile'])) {
        return;
    }

    Plugin::registerClass('PluginEternityTab', [
        'addtabon' => ['Ticket', 'Computer', 'Problem', 'Change'],
    ]);
}

function plugin_version_eternity() {
    return [
        'name'         => 'Eternity SecOps',
        'version'      => PLUGIN_ETERNITY_VERSION,
        'author'       => 'Eternity SecOps',
        'license'      => 'MIT',
        'homepage'     => 'https://eternity.io',
        'minGlpiVersion' => PLUGIN_ETERNITY_MIN_GLPI,
    ];
}

function plugin_eternity_check_prerequisites() {
    return version_compare(GLPI_VERSION, PLUGIN_ETERNITY_MIN_GLPI, '>=');
}

function plugin_eternity_check_config($verbose = false) {
    return true;
}
