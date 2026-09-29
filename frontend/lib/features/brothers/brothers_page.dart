import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/models/api_models.dart';
import '../../core/network/api_repository.dart';
import '../../core/theme/app_theme.dart';

class BrothersPage extends StatefulWidget {
  const BrothersPage(
      {required this.account, required this.repository, super.key});

  final CurrentAccount account;
  final ApiRepository repository;

  @override
  State<BrothersPage> createState() => _BrothersPageState();
}

class _BrothersPageState extends State<BrothersPage> {
  List<Brother> _brothers = const [];
  String _search = '';
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
      final values = await widget.repository.brothers();
      if (!mounted) return;
      setState(() {
        _brothers = values;
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

  List<Brother> get _visible => _brothers
      .where((brother) =>
          '${brother.fullName} ${brother.phone} ${brother.address}'
              .toLowerCase()
              .contains(_search))
      .toList(growable: false);

  @override
  Widget build(BuildContext context) => RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(18, 14, 18, 28),
          children: [
            Text(
              widget.account.role == AppRole.leader
                  ? 'Mi grupo pastoral'
                  : 'Directorio pastoral',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 5),
            Text('Registros visibles dentro de tu alcance',
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(color: AppColors.muted)),
            const SizedBox(height: 14),
            TextField(
              onChanged: (value) =>
                  setState(() => _search = value.trim().toLowerCase()),
              decoration: const InputDecoration(
                prefixIcon: Icon(LucideIcons.search),
                hintText: 'Buscar por nombre, teléfono o dirección',
              ),
            ),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton.icon(
                onPressed: _loading ? null : _create,
                icon: const Icon(LucideIcons.userRoundPlus),
                label: const Text('Nuevo hermano'),
              ),
            ),
            const SizedBox(height: 12),
            if (_error != null) _errorPanel(_error!),
            if (_loading) const LinearProgressIndicator(),
            if (!_loading && _error == null && _visible.isEmpty)
              const _EmptyBrothers(),
            if (!_loading && _error == null)
              for (final brother in _visible) _brotherCard(brother),
          ],
        ),
      );

  Widget _brotherCard(Brother brother) => Card(
        margin: const EdgeInsets.only(bottom: 10),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  CircleAvatar(
                    radius: 20,
                    backgroundColor:
                        brother.active ? AppColors.soft : AppColors.line,
                    child: Text(
                      brother.name.characters.first.toUpperCase(),
                      style: const TextStyle(
                          color: AppColors.forest, fontWeight: FontWeight.w800),
                    ),
                  ),
                  const SizedBox(width: 11),
                  Expanded(
                      child: Text(brother.fullName,
                          style: Theme.of(context).textTheme.titleMedium)),
                  _StatusBadge(active: brother.active),
                  PopupMenuButton<String>(
                    tooltip: 'Acciones del hermano',
                    onSelected: (action) {
                      if (action == 'edit') _edit(brother);
                      if (action == 'assign') _reassign(brother);
                      if (action == 'deactivate') _deactivate(brother);
                    },
                    itemBuilder: (context) => [
                      if (brother.active)
                        const PopupMenuItem(
                            value: 'edit', child: Text('Editar datos')),
                      if (brother.active &&
                          widget.account.role != AppRole.leader)
                        const PopupMenuItem(
                            value: 'assign', child: Text('Reasignar líder')),
                      if (brother.active)
                        const PopupMenuItem(
                            value: 'deactivate', child: Text('Desactivar')),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 12,
                runSpacing: 8,
                children: [
                  _Detail(icon: LucideIcons.phone, text: brother.phone),
                  _Detail(icon: LucideIcons.mapPin, text: brother.address),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                'Asignación ${brother.leaderId.substring(0, 8)}',
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: AppColors.muted),
              ),
            ],
          ),
        ),
      );

  Future<void> _create() async {
    final admin = widget.account.role == AppRole.admin;
    final pastor = widget.account.role == AppRole.pastor;
    try {
      final districts =
          admin ? await widget.repository.districts() : const <District>[];
      final churches =
          admin ? await widget.repository.churches() : const <Church>[];
      final leaders = widget.account.role == AppRole.leader
          ? const <OperatorProfile>[]
          : await widget.repository.operators('LIDER');
      if (!mounted) return;
      String? initialDistrict = widget.account.districtId;
      String? initialChurch = widget.account.churchId;
      if (admin) {
        final districtsWithActiveChurches = districts
            .where((district) => churches.any(
                (church) => church.districtId == district.id && church.active))
            .toList();
        if (districtsWithActiveChurches.isEmpty) {
          _message('Crea primero un distrito y una iglesia activa.');
          return;
        }
        initialDistrict = districtsWithActiveChurches.first.id;
        initialChurch = churches
            .firstWhere((church) =>
                church.districtId == initialDistrict && church.active)
            .id;
      }
      if (pastor && leaders.isNotEmpty) {
        initialDistrict = leaders.first.districtId;
        initialChurch = leaders.first.churchId;
      }
      final values = await _brotherForm(
        districts: districts,
        churches: churches,
        leaders: leaders,
        initialDistrict: initialDistrict,
        initialChurch: initialChurch,
        leaderRequired: widget.account.role != AppRole.leader,
      );
      if (values == null) return;
      await widget.repository.createBrother(
        name: values.name,
        surname: values.surname,
        phone: values.phone,
        address: values.address,
        districtId: values.districtId,
        churchId: values.churchId,
        leaderId:
            widget.account.role == AppRole.leader ? null : values.leaderId,
      );
      await _load();
    } on Object catch (error) {
      _message(apiErrorMessage(error));
    }
  }

  Future<void> _edit(Brother brother) async {
    final name = TextEditingController(text: brother.name);
    final surname = TextEditingController(text: brother.surname);
    final phone = TextEditingController(text: brother.phone);
    final address = TextEditingController(text: brother.address);
    final result = await showDialog<Map<String, String>>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Editar hermano'),
        content: SingleChildScrollView(
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
                  controller: phone,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(labelText: 'Teléfono')),
              const SizedBox(height: 10),
              TextField(
                  controller: address,
                  decoration: const InputDecoration(labelText: 'Dirección')),
            ],
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancelar')),
          FilledButton(
            onPressed: () {
              if (name.text.trim().isNotEmpty &&
                  surname.text.trim().isNotEmpty &&
                  phone.text.trim().isNotEmpty &&
                  address.text.trim().isNotEmpty) {
                Navigator.pop(dialogContext, {
                  'name': name.text.trim(),
                  'surname': surname.text.trim(),
                  'phone': phone.text.trim(),
                  'address': address.text.trim(),
                });
              }
            },
            child: const Text('Guardar'),
          ),
        ],
      ),
    );
    name.dispose();
    surname.dispose();
    phone.dispose();
    address.dispose();
    if (result == null) return;
    try {
      await widget.repository.updateBrother(brother.id, result);
      await _load();
    } on Object catch (error) {
      _message(apiErrorMessage(error));
    }
  }

  Future<_BrotherForm?> _brotherForm({
    required List<District> districts,
    required List<Church> churches,
    required List<OperatorProfile> leaders,
    required String? initialDistrict,
    required String? initialChurch,
    required bool leaderRequired,
  }) async {
    final name = TextEditingController();
    final surname = TextEditingController();
    final phone = TextEditingController();
    final address = TextEditingController();
    String? districtId = initialDistrict;
    String? churchId = initialChurch;
    String? leaderId = leaders
        .where((leader) => leader.churchId == initialChurch && leader.active)
        .firstOrNull
        ?.id;
    final result = await showDialog<_BrotherForm>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, refresh) => AlertDialog(
          title: const Text('Registrar hermano'),
          content: SizedBox(
            width: 470,
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
                      controller: phone,
                      keyboardType: TextInputType.phone,
                      decoration: const InputDecoration(labelText: 'Teléfono')),
                  const SizedBox(height: 10),
                  TextField(
                    controller: address,
                    decoration: const InputDecoration(labelText: 'Dirección'),
                  ),
                  if (widget.account.role == AppRole.admin) ...[
                    const SizedBox(height: 10),
                    DropdownButtonFormField<String>(
                      value: districtId,
                      decoration: const InputDecoration(labelText: 'Distrito'),
                      items: [
                        for (final item in districts)
                          DropdownMenuItem(
                              value: item.id, child: Text(item.name))
                      ],
                      onChanged: (value) => refresh(() {
                        districtId = value;
                        final matching = churches.where((church) =>
                            church.districtId == value && church.active);
                        churchId = matching.firstOrNull?.id;
                        leaderId = leaders
                            .where((leader) =>
                                leader.churchId == churchId && leader.active)
                            .firstOrNull
                            ?.id;
                      }),
                    ),
                    const SizedBox(height: 10),
                    DropdownButtonFormField<String>(
                      value: churchId,
                      decoration: const InputDecoration(labelText: 'Iglesia'),
                      items: [
                        for (final item in churches.where((church) =>
                            church.districtId == districtId && church.active))
                          DropdownMenuItem(
                              value: item.id, child: Text(item.name))
                      ],
                      onChanged: (value) => refresh(() {
                        churchId = value;
                        leaderId = leaders
                            .where((leader) =>
                                leader.churchId == churchId && leader.active)
                            .firstOrNull
                            ?.id;
                      }),
                    ),
                  ] else
                    const _ScopeCard(
                        text:
                            'Se asignará a la iglesia vinculada a tu cuenta.'),
                  if (leaderRequired) ...[
                    const SizedBox(height: 10),
                    DropdownButtonFormField<String>(
                      value: leaderId,
                      decoration:
                          const InputDecoration(labelText: 'Líder asignado'),
                      items: [
                        for (final item in leaders.where((leader) =>
                            leader.churchId == churchId && leader.active))
                          DropdownMenuItem(
                              value: item.id, child: Text(item.fullName))
                      ],
                      onChanged: (value) => refresh(() => leaderId = value),
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
                    phone.text.trim().isEmpty ||
                    address.text.trim().isEmpty ||
                    districtId == null ||
                    churchId == null ||
                    (leaderRequired && leaderId == null)) return;
                Navigator.pop(
                    dialogContext,
                    _BrotherForm(
                      name: name.text.trim(),
                      surname: surname.text.trim(),
                      phone: phone.text.trim(),
                      address: address.text.trim(),
                      districtId: districtId!,
                      churchId: churchId!,
                      leaderId: leaderId,
                    ));
              },
              child: const Text('Registrar'),
            ),
          ],
        ),
      ),
    );
    name.dispose();
    surname.dispose();
    phone.dispose();
    address.dispose();
    return result;
  }

  Future<void> _reassign(Brother brother) async {
    try {
      final leaders = await widget.repository.operators('LIDER');
      final scoped = leaders
          .where(
              (leader) => leader.churchId == brother.churchId && leader.active)
          .toList();
      if (!mounted) return;
      if (scoped.isEmpty) {
        _message('No hay líderes activos en esta iglesia.');
        return;
      }
      String? selected = scoped.first.id;
      final leaderId = await showDialog<String>(
        context: context,
        builder: (dialogContext) => StatefulBuilder(
          builder: (context, refresh) => AlertDialog(
            title: const Text('Reasignar líder'),
            content: DropdownButtonFormField<String>(
              value: selected,
              items: [
                for (final leader in scoped)
                  DropdownMenuItem(
                      value: leader.id, child: Text(leader.fullName))
              ],
              onChanged: (value) => refresh(() => selected = value),
            ),
            actions: [
              TextButton(
                  onPressed: () => Navigator.pop(dialogContext),
                  child: const Text('Cancelar')),
              FilledButton(
                  onPressed: () => Navigator.pop(dialogContext, selected),
                  child: const Text('Reasignar')),
            ],
          ),
        ),
      );
      if (leaderId == null) return;
      await widget.repository.reassignBrother(brother.id, leaderId);
      await _load();
    } on Object catch (error) {
      _message(apiErrorMessage(error));
    }
  }

  Future<void> _deactivate(Brother brother) async {
    final accepted = await showDialog<bool>(
          context: context,
          builder: (dialogContext) => AlertDialog(
            title: const Text('Desactivar hermano'),
            content: Text(
                'Se conservarán las visitas y asignaciones históricas de ${brother.fullName}.'),
            actions: [
              TextButton(
                  onPressed: () => Navigator.pop(dialogContext, false),
                  child: const Text('Cancelar')),
              FilledButton(
                  onPressed: () => Navigator.pop(dialogContext, true),
                  child: const Text('Desactivar')),
            ],
          ),
        ) ??
        false;
    if (!accepted) return;
    try {
      await widget.repository.deactivateBrother(brother.id);
      await _load();
    } on Object catch (error) {
      _message(apiErrorMessage(error));
    }
  }

  void _message(String message) {
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(message)));
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

class _BrotherForm {
  const _BrotherForm({
    required this.name,
    required this.surname,
    required this.phone,
    required this.address,
    required this.districtId,
    required this.churchId,
    this.leaderId,
  });

  final String name;
  final String surname;
  final String phone;
  final String address;
  final String districtId;
  final String churchId;
  final String? leaderId;
}

class _Detail extends StatelessWidget {
  const _Detail({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 15, color: AppColors.pine),
          const SizedBox(width: 5),
          ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 250),
              child: Text(text, overflow: TextOverflow.ellipsis)),
        ],
      );
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.active});

  final bool active;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
        decoration: BoxDecoration(
          color: active ? AppColors.mint.withOpacity(.5) : AppColors.soft,
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(active ? 'ACTIVO' : 'INACTIVO',
            style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800)),
      );
}

class _ScopeCard extends StatelessWidget {
  const _ScopeCard({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
            color: AppColors.soft, borderRadius: BorderRadius.circular(6)),
        child: Text(text, style: Theme.of(context).textTheme.bodySmall),
      );
}

class _EmptyBrothers extends StatelessWidget {
  const _EmptyBrothers();

  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.only(top: 38),
        child: Column(
          children: [
            Icon(LucideIcons.contactRound, size: 28, color: AppColors.pine),
            SizedBox(height: 10),
            Text('No hay hermanos en este alcance.'),
          ],
        ),
      );
}
