import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/models/api_models.dart';
import '../../core/network/api_repository.dart';
import '../../core/theme/app_theme.dart';

class TerritoriesPage extends StatefulWidget {
  const TerritoriesPage({required this.repository, super.key});

  final ApiRepository repository;

  @override
  State<TerritoriesPage> createState() => _TerritoriesPageState();
}

class _TerritoriesPageState extends State<TerritoriesPage> {
  bool _showChurches = false;
  String _search = '';
  List<District> _districts = const [];
  List<Church> _churches = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait<Object>([
        widget.repository.districts(),
        widget.repository.churches(),
      ]);
      if (!mounted) return;
      setState(() {
        _districts = results[0] as List<District>;
        _churches = results[1] as List<Church>;
        _loading = false;
      });
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _error = apiErrorMessage(error);
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) => RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(18, 14, 18, 28),
          children: [
            Text('Administración territorial',
                style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 5),
            Text('Distritos e iglesias · Solo ADMIN',
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(color: AppColors.muted)),
            const SizedBox(height: 18),
            SegmentedButton<bool>(
              segments: [
                ButtonSegment(
                    value: false,
                    label: Text('Distritos (${_districts.length})'),
                    icon: const Icon(LucideIcons.map)),
                ButtonSegment(
                    value: true,
                    label: Text('Iglesias (${_churches.length})'),
                    icon: const Icon(LucideIcons.church)),
              ],
              selected: {_showChurches},
              onSelectionChanged: (selection) =>
                  setState(() => _showChurches = selection.first),
            ),
            const SizedBox(height: 12),
            TextField(
              onChanged: (value) =>
                  setState(() => _search = value.trim().toLowerCase()),
              decoration: const InputDecoration(
                prefixIcon: Icon(LucideIcons.search),
                hintText: 'Buscar territorio',
              ),
            ),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton.icon(
                onPressed: _loading ? null : _create,
                icon: const Icon(LucideIcons.plus),
                label: Text(_showChurches ? 'Nueva iglesia' : 'Nuevo distrito'),
              ),
            ),
            const SizedBox(height: 14),
            if (_error != null) _errorPanel(_error!),
            if (_loading) const LinearProgressIndicator(),
            if (!_loading && _error == null)
              if (_showChurches)
                ..._visibleChurches.map(_churchTile)
              else
                ..._visibleDistricts.map(_districtTile),
            if (!_loading && _error == null && _visibleCount == 0) _emptyState,
          ],
        ),
      );

  List<District> get _visibleDistricts => _districts
      .where((district) => district.name.toLowerCase().contains(_search))
      .toList(growable: false);

  List<Church> get _visibleChurches => _churches.where((church) {
        final district = _districtById(church.districtId)?.name ?? '';
        return '${church.name} $district'.toLowerCase().contains(_search);
      }).toList(growable: false);

  int get _visibleCount =>
      _showChurches ? _visibleChurches.length : _visibleDistricts.length;

  Widget get _emptyState => Padding(
        padding: const EdgeInsets.only(top: 42),
        child: Column(
          children: [
            const Icon(LucideIcons.mapPinned, size: 30, color: AppColors.pine),
            const SizedBox(height: 10),
            Text(_search.isEmpty
                ? 'No hay registros territoriales'
                : 'Sin resultados'),
          ],
        ),
      );

  Widget _districtTile(District district) {
    final churches =
        _churches.where((church) => church.districtId == district.id).toList();
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(LucideIcons.mapPinned, color: AppColors.pine),
                const SizedBox(width: 10),
                Expanded(
                    child: Text(district.name,
                        style: Theme.of(context).textTheme.titleLarge)),
                IconButton(
                  tooltip: 'Editar distrito',
                  onPressed: () => _editDistrict(district),
                  icon: const Icon(LucideIcons.pencil, size: 19),
                ),
                IconButton(
                  tooltip: churches.isEmpty
                      ? 'Eliminar distrito'
                      : 'Tiene iglesias asociadas',
                  onPressed:
                      churches.isEmpty ? () => _deleteDistrict(district) : null,
                  icon: const Icon(LucideIcons.trash2, size: 19),
                ),
              ],
            ),
            Text(
                '${churches.length} ${churches.length == 1 ? 'iglesia asociada' : 'iglesias asociadas'}',
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: AppColors.muted)),
            if (churches.isNotEmpty) ...[
              const SizedBox(height: 10),
              const Divider(height: 1),
              for (final church in churches.take(4))
                ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(LucideIcons.church,
                      size: 18,
                      color: church.active ? AppColors.pine : AppColors.muted),
                  title: Text(church.name),
                  subtitle: Text(church.active ? 'Activa' : 'Inactiva'),
                  trailing: church.active
                      ? null
                      : const Icon(LucideIcons.circleX, size: 17),
                ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _churchTile(Church church) => Card(
        margin: const EdgeInsets.only(bottom: 10),
        child: ListTile(
          leading: Icon(LucideIcons.church,
              color: church.active ? AppColors.pine : AppColors.muted),
          title: Text(church.name),
          subtitle: Text(
              '${_districtById(church.districtId)?.name ?? 'Distrito'} · ${church.address ?? 'Sin dirección'}'),
          trailing: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              _StatusTag(
                  text: church.active ? 'Activa' : 'Inactiva',
                  active: church.active),
              const SizedBox(width: 4),
              IconButton(
                tooltip: 'Editar iglesia',
                onPressed: church.active ? () => _editChurch(church) : null,
                icon: const Icon(LucideIcons.pencil, size: 18),
              ),
              IconButton(
                tooltip:
                    church.active ? 'Desactivar iglesia' : 'Ya está inactiva',
                onPressed:
                    church.active ? () => _deactivateChurch(church) : null,
                icon: const Icon(LucideIcons.trash2, size: 18),
              ),
            ],
          ),
        ),
      );

  District? _districtById(String id) {
    for (final district in _districts) {
      if (district.id == id) return district;
    }
    return null;
  }

  Future<void> _create() async {
    if (_showChurches) {
      if (_districts.isEmpty) {
        _message('Primero crea un distrito.');
        return;
      }
      final values = await _churchForm();
      if (values == null) return;
      await _run(() => widget.repository.createChurch(
            districtId: values.$1,
            name: values.$2,
            address: values.$3,
          ));
      return;
    }
    final name = await _nameDialog(title: 'Nuevo distrito');
    if (name != null) await _run(() => widget.repository.createDistrict(name));
  }

  Future<void> _editDistrict(District district) async {
    final name =
        await _nameDialog(title: 'Editar distrito', initial: district.name);
    if (name != null) {
      await _run(() => widget.repository.updateDistrict(district.id, name));
    }
  }

  Future<void> _editChurch(Church church) async {
    var name = church.name;
    var address = church.address ?? '';
    final saved = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Editar iglesia'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextFormField(
              initialValue: name,
              onChanged: (value) => name = value,
                decoration: const InputDecoration(labelText: 'Nombre')),
            const SizedBox(height: 12),
            TextFormField(
              initialValue: address,
              onChanged: (value) => address = value,
                decoration: const InputDecoration(labelText: 'Dirección')),
            const SizedBox(height: 8),
            Align(
                alignment: Alignment.centerLeft,
                child: Text(
                    'Distrito: ${_districtById(church.districtId)?.name ?? ''}')),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancelar')),
          FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Guardar')),
        ],
      ),
    );
    if (saved == true && name.trim().isNotEmpty) {
      await _run(() => widget.repository.updateChurch(
            church.id,
            name: name.trim(),
            address: address.trim(),
          ));
    }
  }

  Future<void> _deleteDistrict(District district) async {
    final accepted = await _confirm(
      title: 'Eliminar distrito',
      message:
          'Se eliminará “${district.name}”. Esta acción no se puede deshacer.',
    );
    if (accepted) {
      await _run(() => widget.repository.deleteDistrict(district.id));
    }
  }

  Future<void> _deactivateChurch(Church church) async {
    final accepted = await _confirm(
      title: 'Desactivar iglesia',
      message:
          'La iglesia conservará su historial. Debe no tener usuarios activos.',
    );
    if (accepted) {
      await _run(() => widget.repository.deactivateChurch(church.id));
    }
  }

  Future<void> _run(Future<Object?> Function() action) async {
    try {
      await action();
      if (!mounted) return;
      await _load();
    } on Object catch (error) {
      _message(apiErrorMessage(error));
    }
  }

  Future<String?> _nameDialog(
      {required String title, String initial = ''}) async {
    var name = initial;
    final result = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(title),
        content: TextFormField(
          initialValue: initial,
          onChanged: (value) => name = value,
            autofocus: true,
            decoration: const InputDecoration(labelText: 'Nombre')),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancelar')),
          FilledButton(
              onPressed: () => Navigator.pop(dialogContext, name.trim()),
              child: const Text('Guardar')),
        ],
      ),
    );
    if (result == null || result.trim().isEmpty) return null;
    return result.trim();
  }

  Future<(String, String, String?)?> _churchForm() async {
    String? districtId = _districts.first.id;
    var name = '';
    var address = '';
    final result = await showDialog<(String, String, String?)>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, refresh) => AlertDialog(
          title: const Text('Nueva iglesia'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<String>(
                value: districtId,
                decoration: const InputDecoration(labelText: 'Distrito'),
                items: [
                  for (final d in _districts)
                    DropdownMenuItem(value: d.id, child: Text(d.name))
                ],
                onChanged: (value) => refresh(() => districtId = value),
              ),
              const SizedBox(height: 12),
              TextField(
                  onChanged: (value) => name = value,
                  decoration: const InputDecoration(labelText: 'Nombre')),
              const SizedBox(height: 12),
              TextField(
                  onChanged: (value) => address = value,
                  decoration: const InputDecoration(labelText: 'Dirección')),
            ],
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Cancelar')),
            FilledButton(
              onPressed: () {
                if (districtId != null && name.trim().isNotEmpty) {
                  Navigator.pop(dialogContext, (
                    districtId!,
                    name.trim(),
                    address.trim().isEmpty ? null : address.trim()
                  ));
                }
              },
              child: const Text('Crear'),
            ),
          ],
        ),
      ),
    );
    return result;
  }

  Future<bool> _confirm(
          {required String title, required String message}) async =>
      await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: Text(title),
          content: Text(message),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(dialogContext, false),
                child: const Text('Cancelar')),
            FilledButton(
                onPressed: () => Navigator.pop(dialogContext, true),
                child: const Text('Confirmar')),
          ],
        ),
      ) ??
      false;

  void _message(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  Widget _errorPanel(String message) => Card(
        color: AppColors.coralSoft,
        child: ListTile(
          leading:
              const Icon(LucideIcons.triangleAlert, color: AppColors.coral),
          title: Text(message),
          trailing: IconButton(
              onPressed: _load, icon: const Icon(LucideIcons.refreshCw)),
        ),
      );
}

class _StatusTag extends StatelessWidget {
  const _StatusTag({required this.text, required this.active});

  final String text;
  final bool active;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
        decoration: BoxDecoration(
          color: active ? AppColors.mint.withOpacity(.45) : AppColors.soft,
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(text,
            style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700)),
      );
}
