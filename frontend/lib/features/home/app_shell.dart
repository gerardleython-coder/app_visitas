import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/models/api_models.dart';
import '../../core/network/api_repository.dart';
import '../../core/theme/app_theme.dart';
import '../brothers/brothers_page.dart';
import '../profile/profile_page.dart';
import '../reports/insights_page.dart';
import '../team/team_page.dart';
import '../territories/territories_page.dart';
import '../visits/visits_page.dart';
import 'overview_page.dart';

class AppShell extends StatefulWidget {
  const AppShell({
    required this.account,
    required this.repository,
    super.key,
  });

  final CurrentAccount account;
  final ApiRepository repository;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _selectedIndex = 0;

  List<_AppDestination> get _destinations => switch (widget.account.role) {
        AppRole.admin => const [
            _AppDestination(
                'Inicio', LucideIcons.layoutDashboard, _Screen.home),
            _AppDestination(
                'Territorios', LucideIcons.map, _Screen.territories),
            _AppDestination('Equipo', LucideIcons.users, _Screen.team),
            _AppDestination(
                'Hermanos', LucideIcons.contactRound, _Screen.brothers),
            _AppDestination('Más', LucideIcons.menu, _Screen.more),
          ],
        AppRole.pastor => const [
            _AppDestination(
                'Inicio', LucideIcons.layoutDashboard, _Screen.home),
            _AppDestination('Equipo', LucideIcons.users, _Screen.team),
            _AppDestination(
                'Hermanos', LucideIcons.contactRound, _Screen.brothers),
            _AppDestination(
                'Visitas', LucideIcons.calendarDays, _Screen.visits),
            _AppDestination('Más', LucideIcons.menu, _Screen.more),
          ],
        AppRole.leader => const [
            _AppDestination(
                'Inicio', LucideIcons.layoutDashboard, _Screen.home),
            _AppDestination(
                'Mis visitas', LucideIcons.calendarDays, _Screen.visits),
            _AppDestination('Mi grupo', LucideIcons.users, _Screen.brothers),
            _AppDestination('Más', LucideIcons.menu, _Screen.more),
          ],
      };

  Widget _screen(_Screen screen) => switch (screen) {
        _Screen.home =>
          OverviewPage(account: widget.account, repository: widget.repository),
        _Screen.territories => TerritoriesPage(repository: widget.repository),
        _Screen.team =>
          TeamPage(account: widget.account, repository: widget.repository),
        _Screen.brothers =>
          BrothersPage(account: widget.account, repository: widget.repository),
        _Screen.visits =>
          VisitsPage(account: widget.account, repository: widget.repository),
        _Screen.more => _MorePage(
            account: widget.account,
            repository: widget.repository,
            onOpenProfile: _openProfile,
            onOpenAudit: _openAudit,
            onOpenRanking: _openRanking,
          ),
      };

  void _openProfile() => Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => ProfilePage(
              account: widget.account, repository: widget.repository),
        ),
      );

  void _openAudit() => Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => AuditPage(repository: widget.repository),
        ),
      );

  void _openRanking() => Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => RankingPage(
              account: widget.account, repository: widget.repository),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final destinations = _destinations;
    if (_selectedIndex >= destinations.length) _selectedIndex = 0;
    final width = MediaQuery.sizeOf(context).width;
    final content = _screen(destinations[_selectedIndex].screen);

    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 68,
        titleSpacing: 16,
        title: Row(
          children: [
            SvgPicture.asset('assets/appvisitas_logo.svg',
                width: 38, height: 38),
            const SizedBox(width: 10),
            const Flexible(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('AppVisitas',
                      style: TextStyle(fontWeight: FontWeight.w800)),
                  Text('Gestión pastoral',
                      style: TextStyle(fontSize: 11, color: AppColors.muted)),
                ],
              ),
            ),
            const Spacer(),
            _RoleBadge(role: widget.account.role),
            const SizedBox(width: 8),
            IconButton.filledTonal(
              tooltip: 'Perfil y seguridad',
              onPressed: _openProfile,
              icon: const Icon(LucideIcons.userRound),
            ),
          ],
        ),
      ),
      body: SafeArea(
        top: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1240),
            child: width >= 900
                ? Row(
                    children: [
                      NavigationRail(
                        selectedIndex: _selectedIndex,
                        onDestinationSelected: (index) =>
                            setState(() => _selectedIndex = index),
                        labelType: NavigationRailLabelType.all,
                        destinations: [
                          for (final destination in destinations)
                            NavigationRailDestination(
                              icon: Icon(destination.icon),
                              selectedIcon: Icon(destination.icon),
                              label: Text(destination.label),
                            ),
                        ],
                      ),
                      const VerticalDivider(width: 1),
                      Expanded(child: content),
                    ],
                  )
                : content,
          ),
        ),
      ),
      bottomNavigationBar: width >= 900
          ? null
          : NavigationBar(
              selectedIndex: _selectedIndex,
              onDestinationSelected: (index) =>
                  setState(() => _selectedIndex = index),
              destinations: [
                for (final destination in destinations)
                  NavigationDestination(
                    icon: Icon(destination.icon),
                    label: destination.label,
                  ),
              ],
            ),
    );
  }
}

class _RoleBadge extends StatelessWidget {
  const _RoleBadge({required this.role});

  final AppRole role;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
        decoration: BoxDecoration(
          color: AppColors.mint.withOpacity(0.55),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(
          role.apiValue,
          style: const TextStyle(
            color: AppColors.forest,
            fontSize: 11,
            fontWeight: FontWeight.w800,
          ),
        ),
      );
}

class _AppDestination {
  const _AppDestination(this.label, this.icon, this.screen);

  final String label;
  final IconData icon;
  final _Screen screen;
}

enum _Screen { home, territories, team, brothers, visits, more }

class _MorePage extends StatelessWidget {
  const _MorePage({
    required this.account,
    required this.repository,
    required this.onOpenProfile,
    required this.onOpenAudit,
    required this.onOpenRanking,
  });

  final CurrentAccount account;
  final ApiRepository repository;
  final VoidCallback onOpenProfile;
  final VoidCallback onOpenAudit;
  final VoidCallback onOpenRanking;

  @override
  Widget build(BuildContext context) {
    final options = <(String, String, IconData, VoidCallback)>[
      if (account.role != AppRole.leader)
        (
          'Auditoría pastoral',
          'Consulta eventos según tu alcance',
          LucideIcons.clipboardList,
          onOpenAudit
        ),
      if (account.role != AppRole.leader)
        (
          'Ranking',
          'Visitas completadas por período',
          LucideIcons.chartNoAxesCombined,
          onOpenRanking
        ),
      (
        'Perfil y seguridad',
        account.email,
        LucideIcons.userRound,
        onOpenProfile
      ),
    ];
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('Más opciones', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 16),
        for (final option in options)
          Card(
            child: ListTile(
              leading: Icon(option.$3, color: AppColors.pine),
              title: Text(option.$1),
              subtitle: Text(option.$2),
              trailing: const Icon(LucideIcons.chevronRight),
              onTap: option.$4,
            ),
          ),
      ],
    );
  }
}
