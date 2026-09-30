import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/models/api_models.dart';
import '../../core/network/api_repository.dart';
import '../../core/theme/app_theme.dart';

class TeamPage extends StatefulWidget {
  const TeamPage({required this.account, required this.repository, super.key});

  final CurrentAccount account;
  final ApiRepository repository;

  @override
  State<TeamPage> createState() => _TeamPageState();
}

class _TeamPageState extends State<TeamPage> {
  String _role = 'LIDER';
  String _search = '';
  List<OperatorProfile> _operators = const [];
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
      if (widget.account.role == AppRole.admin && _role == 'ADMIN') {
        final administrators = await widget.repository.administrators();
        if (!mounted) return;
        setState(() {
          _operators = administrators;
          _districts = const [];
          _churches = const [];
          _loading = false;
        });
        return;
      }

      final operatorFuture = widget.repository.operators(_role);
      if (widget.account.role == AppRole.admin) {
        final response = await Future.wait<Object>([
          operatorFuture,
          widget.repository.districts(),
          widget.repository.churches(),
        ]);
        if (!mounted) return;
        setState(() {
          _operators = response[0] as List<OperatorProfile>;
          _districts = response[1] as List<District>;
          _churches = response[2] as List<Church>;
          _loading = false;
        });
      } else {
        final result = await operatorFuture;
        if (!mounted) return;
        setState(() {
          _operators = result;
          _loading = false;
        });
      }
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _error = apiErrorMessage(error);
        _loading = false;
      });
    }
  }

  List<OperatorProfile> get _visible => _operators
      .where((item) =>
          '${item.fullName} ${item.email}'.toLowerCase().contains(_search))
      .toList(growable: false);

  @override
  Widget build(BuildContext context) => RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(18, 14, 18, 28),
          children: [
            Text(_role == 'ADMIN' ? 'Administradores' : 'Equipo pastoral',
                style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 5),
            Text(
              widget.account.role == AppRole.admin
                  ? _role == 'ADMIN'
                      ? 'Cuentas administrativas'
                      : 'Cuentas y asignaciones de distrito'
                  : 'Líderes de tu iglesia',
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: AppColors.muted),
            ),
            const SizedBox(height: 16),
            if (widget.account.role == AppRole.admin)
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'ADMIN', label: Text('Admins')),
                  ButtonSegment(value: 'PASTOR', label: Text('Pastores')),
                  ButtonSegment(value: 'LIDER', label: Text('Líderes')),
                ],
                selected: {_role},
                onSelectionChanged: (selection) {
                  setState(() => _role = selection.first);
                  _load();
                },
              ),
            const SizedBox(height: 12),
            TextField(
              onChanged: (value) =>
                  setState(() => _search = value.trim().toLowerCase()),
              decoration: const InputDecoration(
                prefixIcon: Icon(LucideIcons.search),
                hintText: 'Buscar por nombre o correo',
              ),
            ),
            if (widget.account.role == AppRole.admin) ...[
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton.icon(
                  onPressed: _loading ? null : _create,
                  icon: const Icon(LucideIcons.userRoundPlus),
                  label: Text(switch (_role) {
                    'ADMIN' => 'Nuevo administrador',
                    'PASTOR' => 'Nuevo pastor',
                    _ => 'Nuevo líder',
                  }),
                ),
              ),
            ],
            const SizedBox(height: 14),
            if (_error != null) _errorPanel(_error!),
            if (_loading) const LinearProgressIndicator(),
            if (!_loading && _error == null && _visible.isEmpty)
              const _EmptyTeam(),
            if (!_loading && _error == null)
              for (final operator in _visible) _operatorCard(operator),
          ],
        ),
      );

  Widget _operatorCard(OperatorProfile item) => Card(
        margin: const EdgeInsets.only(bottom: 10),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  CircleAvatar(
                    radius: 21,
                    backgroundColor: AppColors.soft,
                    child: Text(
                      item.name.characters.first.toUpperCase(),
                      style: const TextStyle(
                          color: AppColors.forest, fontWeight: FontWeight.w800),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(item.fullName,
                            style: Theme.of(context).textTheme.titleMedium),
                        Text(item.email,
                            style: Theme.of(context)
                                .textTheme
                                .bodySmall
                                ?.copyWith(color: AppColors.muted)),
                      ],
                    ),
                  ),
                  if (item.isPrimaryPastor) const _PrimaryBadge(),
                  if (item.role != 'ADMIN' || item.active)
                    PopupMenuButton<String>(
                      tooltip: 'Acciones de usuario',
                      onSelected: (action) =>
                          action == 'edit' ? _edit(item) : _deactivate(item),
                      itemBuilder: (context) => [
                        const PopupMenuItem(
                            value: 'edit', child: Text('Editar datos')),
                        if (item.active &&
                            widget.account.role == AppRole.admin &&
                            (item.role != 'ADMIN' ||
                                (item.id != widget.account.id &&
                                    _operators
                                            .where((profile) =>
                                                profile.role == 'ADMIN' &&
                                                profile.active)
                                            .length >
                                        1)))
                          const PopupMenuItem(
                              value: 'deactivate', child: Text('Desactivar')),
                      ],
                    ),
                ],
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  if (item.churchId != null)
                    _MetaChip(
                        icon: LucideIcons.building2,
                        label: _churchName(item.churchId)),
                  if (item.districtId != null)
                    _MetaChip(
                        icon: LucideIcons.mapPinned,
                        label: _districtName(item.districtId)),
                  _MetaChip(
                    icon: item.active
                        ? LucideIcons.circleCheck
                        : LucideIcons.circleX,
                    label: item.active ? 'Activo' : 'Inactivo',
                  ),
                ],
              ),
              if (_role == 'PASTOR' &&
                  widget.account.role == AppRole.admin &&
                  item.active &&
                  !item.isPrimaryPastor) ...[
                const SizedBox(height: 8),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    onPressed: () => _setPrimary(item),
                    icon: const Icon(LucideIcons.badgeCheck, size: 18),
                    label: const Text('Definir como pastor principal'),
                  ),
                ),
              ],
            ],
          ),
        ),
      );

  String _churchName(String? id) {
    for (final church in _churches) {
      if (church.id == id) return church.name;
    }
    return widget.account.role == AppRole.pastor
        ? 'Iglesia asignada'
        : 'Iglesia';
  }

  String _districtName(String? id) {
    for (final district in _districts) {
      if (district.id == id) return district.name;
    }
    return widget.account.role == AppRole.pastor
        ? 'Distrito asignado'
        : 'Distrito';
  }

  Future<void> _create() async {
    if (_role == 'ADMIN') {
      final form = await _administratorForm();
      if (form == null) return;
      try {
        await widget.repository.createAdministrator(
          name: form.name,
          surname: form.surname,
          email: form.email,
          password: form.password,
        );
        await _load();
      } on Object catch (error) {
        _message(apiErrorMessage(error));
      }
      return;
    }

    final activeChurches = _churches.where((church) => church.active).toList();
    final availableDistricts = _districts
        .where((district) =>
            activeChurches.any((church) => church.districtId == district.id))
        .toList();
    if (availableDistricts.isEmpty || activeChurches.isEmpty) {
      _message('Crea primero un distrito y una iglesia activa.');
      return;
    }
    final form = await _operatorForm();
    if (form == null) return;
    try {
      await widget.repository.createOperator(
        role: _role,
        name: form.name,
        surname: form.surname,
        email: form.email,
        password: form.password,
        districtId: form.districtId!,
        churchId: form.churchId!,
      );
      await _load();
    } on Object catch (error) {
      _message(apiErrorMessage(error));
    }
  }

  Future<void> _edit(OperatorProfile item) async {
    if (item.role == 'ADMIN') {
      final form = await _administratorForm(existing: item);
      if (form == null) return;
      try {
        await widget.repository.updateAdministrator(item.id, {
          'name': form.name,
          'surname': form.surname,
          'email': form.email,
        });
        await _load();
      } on Object catch (error) {
        _message(apiErrorMessage(error));
      }
      return;
    }

    final form = await _operatorForm(existing: item);
    if (form == null) return;
    try {
      await widget.repository.updateOperator(item.id, item.role, {
        'name': form.name,
        'surname': form.surname,
        'email': form.email,
      });
      await _load();
    } on Object catch (error) {
      _message(apiErrorMessage(error));
    }
  }

  Future<_OperatorForm?> _administratorForm({
    OperatorProfile? existing,
  }) async {
    var name = existing?.name ?? '';
    var surname = existing?.surname ?? '';
    var email = existing?.email ?? '';
    var password = '';
    final result = await showDialog<_OperatorForm>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, refresh) => AlertDialog(
          title: Text(existing == null
              ? 'Nuevo administrador'
              : 'Editar administrador'),
          content: SizedBox(
            width: 460,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  initialValue: name,
                  onChanged: (value) => name = value,
                  decoration: const InputDecoration(labelText: 'Nombre'),
                ),
                const SizedBox(height: 10),
                TextFormField(
                  initialValue: surname,
                  onChanged: (value) => surname = value,
                  decoration: const InputDecoration(labelText: 'Apellido'),
                ),
                const SizedBox(height: 10),
                TextFormField(
                  initialValue: email,
                  onChanged: (value) => email = value,
                  keyboardType: TextInputType.emailAddress,
                  decoration: const InputDecoration(labelText: 'Correo'),
                ),
                if (existing == null) ...[
                  const SizedBox(height: 10),
                  TextFormField(
                    initialValue: password,
                    onChanged: (value) => password = value,
                    obscureText: true,
                    decoration:
                        const InputDecoration(labelText: 'Contraseña inicial'),
                  ),
                ],
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () {
                if (name.trim().isEmpty ||
                    surname.trim().isEmpty ||
                    !email.contains('@') ||
                    (existing == null && password.isEmpty)) return;
                FocusScope.of(dialogContext).unfocus();
                Navigator.pop(
                  dialogContext,
                  _OperatorForm(
                    name: name.trim(),
                    surname: surname.trim(),
                    email: email.trim(),
                    password: password,
                  ),
                );
              },
              child: const Text('Guardar'),
            ),
          ],
        ),
      ),
    );
    return result;
  }

  Future<_OperatorForm?> _operatorForm({OperatorProfile? existing}) async {
    final activeChurches = _churches.where((church) => church.active).toList();
    final availableDistricts = _districts
        .where((district) =>
            activeChurches.any((church) => church.districtId == district.id))
        .toList();
    final name = TextEditingController(text: existing?.name ?? '');
    final surname = TextEditingController(text: existing?.surname ?? '');
    final email = TextEditingController(text: existing?.email ?? '');
    final password = TextEditingController();
    var districtId = existing?.districtId ?? availableDistricts.first.id;
    var churchId = existing?.churchId ??
        activeChurches.firstWhere((item) => item.districtId == districtId).id;
    final result = await showDialog<_OperatorForm>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, refresh) => AlertDialog(
          title: Text(existing == null
              ? (_role == 'PASTOR' ? 'Nuevo pastor' : 'Nuevo líder')
              : 'Editar usuario'),
          content: SizedBox(
            width: 460,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                      controller: name,
                      decoration: const InputDecoration(labelText: 'Nombre')),
                  const SizedBox(height: 10),
                  TextField(
                      controller: surname,
                      decoration: const InputDecoration(labelText: 'Apellido')),
                  const SizedBox(height: 10),
                  TextField(
                      controller: email,
                      keyboardType: TextInputType.emailAddress,
                      decoration: const InputDecoration(
                          labelText: 'Correo institucional')),
                  if (existing == null) ...[
                    const SizedBox(height: 10),
                    TextField(
                        controller: password,
                        obscureText: true,
                        decoration: const InputDecoration(
                            labelText: 'Contraseña inicial')),
                    const SizedBox(height: 10),
                    DropdownButtonFormField<String>(
                      value: districtId,
                      decoration: const InputDecoration(labelText: 'Distrito'),
                      items: [
                        for (final item in availableDistricts)
                          DropdownMenuItem(
                              value: item.id, child: Text(item.name))
                      ],
                      onChanged: (value) => refresh(() {
                        districtId = value!;
                        churchId = activeChurches
                            .firstWhere((church) => church.districtId == value)
                            .id;
                      }),
                    ),
                    const SizedBox(height: 10),
                    DropdownButtonFormField<String>(
                      value: churchId,
                      decoration: const InputDecoration(labelText: 'Iglesia'),
                      items: [
                        for (final item in activeChurches
                            .where((church) => church.districtId == districtId))
                          DropdownMenuItem(
                              value: item.id, child: Text(item.name))
                      ],
                      onChanged: (value) => refresh(() => churchId = value!),
                    ),
                  ],
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Cancelar')),
            FilledButton(
              onPressed: () {
                if (name.text.trim().isEmpty ||
                    surname.text.trim().isEmpty ||
                    !email.text.contains('@')) return;
                if (existing == null && password.text.isEmpty) return;
                Navigator.pop(
                    dialogContext,
                    _OperatorForm(
                      name: name.text.trim(),
                      surname: surname.text.trim(),
                      email: email.text.trim(),
                      password: password.text,
                      districtId: districtId,
                      churchId: churchId,
                    ));
              },
              child: const Text('Guardar'),
            ),
          ],
        ),
      ),
    );
    name.dispose();
    surname.dispose();
    email.dispose();
    password.dispose();
    return result;
  }

  Future<void> _deactivate(OperatorProfile item) async {
    if (!await _confirm('Desactivar ${item.fullName}?')) return;
    try {
      if (item.role == 'ADMIN') {
        await widget.repository.deactivateAdministrator(item.id);
      } else {
        await widget.repository.deactivateOperator(item.id, item.role);
      }
      await _load();
    } on Object catch (error) {
      _message(apiErrorMessage(error));
    }
  }

  Future<void> _setPrimary(OperatorProfile item) async {
    final churchId = item.churchId;
    if (churchId == null) return;
    final accepted = await _confirm(
        'Asignar a ${item.fullName} como pastor principal de ${_churchName(item.churchId)}?');
    if (!accepted) return;
    try {
      await widget.repository.setPrimaryPastor(churchId, item.id);
      await _load();
    } on Object catch (error) {
      _message(apiErrorMessage(error));
    }
  }

  Future<bool> _confirm(String message) async =>
      await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Confirmar acción'),
          content: Text(message),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancelar')),
            FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Confirmar')),
          ],
        ),
      ) ??
      false;

  void _message(String value) {
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(value)));
    }
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

class _OperatorForm {
  const _OperatorForm({
    required this.name,
    required this.surname,
    required this.email,
    required this.password,
    this.districtId,
    this.churchId,
  });

  final String name;
  final String surname;
  final String email;
  final String password;
  final String? districtId;
  final String? churchId;
}

class _MetaChip extends StatelessWidget {
  const _MetaChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
        decoration: BoxDecoration(
            color: AppColors.soft, borderRadius: BorderRadius.circular(4)),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: AppColors.pine),
            const SizedBox(width: 5),
            Text(label,
                style: const TextStyle(fontSize: 11, color: AppColors.text)),
          ],
        ),
      );
}

class _PrimaryBadge extends StatelessWidget {
  const _PrimaryBadge();

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
        decoration: BoxDecoration(
            color: AppColors.mint.withOpacity(.6),
            borderRadius: BorderRadius.circular(4)),
        child: const Text('PRINCIPAL',
            style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800)),
      );
}

class _EmptyTeam extends StatelessWidget {
  const _EmptyTeam();

  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.only(top: 38),
        child: Column(
          children: [
            Icon(LucideIcons.users, size: 28, color: AppColors.pine),
            SizedBox(height: 10),
            Text('No hay usuarios para mostrar.'),
          ],
        ),
      );
}
