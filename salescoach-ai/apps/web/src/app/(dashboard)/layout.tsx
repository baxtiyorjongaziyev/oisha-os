'use client';
import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard, Phone, MessageSquare, BarChart2, Calendar,
  Star, Bell, Settings, ChevronLeft, ChevronRight, ChevronDown,
  Search, Moon, Bug, Building2, User, LogOut, AlertTriangle,
  TrendingUp, Users, ListChecks,
} from 'lucide-react';

const NAV = [
  { href: '/home',           icon: LayoutDashboard, label: 'Bosh sahifa' },
  { href: '/calls',          icon: Phone,            label: 'Qo\'ng\'iroqlar' },
  { href: '/chat',           icon: MessageSquare,    label: 'Chat' },
  {
    label: 'Analitika', icon: BarChart2, children: [
      { href: '/analytics',           label: 'Umumiy ko\'rinish' },
      { href: '/analytics/quality',   label: 'Sifat nazorati' },
      { href: '/analytics/coaching',  label: 'Malaka oshirish' },
      { href: '/analytics/clients',   label: 'Mijoz tahlili' },
      { href: '/analytics/activity',  label: 'Faoliyat tahlili' },
      { href: '/analytics/leads',     label: 'Lid analitikasi' },
    ],
  },
  { href: '/daily-summary',  icon: Calendar,         label: 'Kunlik hisobot' },
  { href: '/lead-summaries', icon: Star,             label: 'Lid xulosalari' },
  { href: '/alerts',         icon: Bell,             label: 'Ogohlantirishlar', badge: 25 },
];

const SETTINGS_NAV = [
  { href: '/settings/profile',      label: 'Profil',            icon: User },
  { href: '/settings/general',      label: 'Umumiy',            icon: Settings },
  { href: '/settings/appearance',   label: 'Ko\'rinish',         icon: Moon },
  { href: '/settings/businesses',   label: 'Bizneslar',         icon: Building2 },
  { href: '/settings/schedule',     label: 'Ish jadvali',       icon: Calendar },
  { href: '/settings/daily-report', label: 'Kunlik hisobot',    icon: BarChart2 },
  { href: '/settings/managers',     label: 'Rahbarlar',         icon: Users },
  { href: '/settings/salespeople',  label: 'Sotuv menejerlari', icon: TrendingUp },
  { href: '/settings/subscription', label: 'Obuna',             icon: Star },
  { href: '/settings/playbook',     label: 'Sotuv mezoni',      icon: ListChecks },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [analyticsOpen, setAnalyticsOpen] = useState(pathname.startsWith('/analytics'));
  const [userOpen, setUserOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);

  const isSettings = pathname.startsWith('/settings');
  const sidebarNav = isSettings ? SETTINGS_NAV : NAV;

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* ── Sidebar ── */}
      <aside style={{
        width: collapsed ? 56 : 'var(--sidebar-w)',
        minWidth: collapsed ? 56 : 'var(--sidebar-w)',
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.2s ease, min-width 0.2s ease',
        overflow: 'hidden',
      }}>
        {/* Logo */}
        <div style={{
          padding: collapsed ? '16px 12px' : '16px 16px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          minHeight: 56,
        }}>
          <div style={{
            width: 28, height: 28, borderRadius: 8,
            background: 'linear-gradient(135deg, var(--accent), var(--accent-violet))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            <Phone size={14} color="white" />
          </div>
          {!collapsed && (
            <div>
              <div style={{ fontWeight: 700, fontSize: '0.9375rem', letterSpacing: '-0.01em' }}>Metasell</div>
              <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginTop: 1 }}>AI Platforma</div>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '8px', overflowY: 'auto', overflowX: 'hidden' }}>
          {!isSettings && (
            <>
              {NAV.map((item) => {
                if ('children' in item) {
                  const isActive = pathname.startsWith('/analytics');
                  return (
                    <div key={item.label}>
                      <div
                        className={`nav-item ${isActive ? 'active' : ''}`}
                        onClick={() => setAnalyticsOpen(v => !v)}
                        style={{ justifyContent: collapsed ? 'center' : 'space-between' }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <item.icon size={16} style={{ flexShrink: 0 }} />
                          {!collapsed && <span>{item.label}</span>}
                        </div>
                        {!collapsed && (
                          <ChevronDown size={13} style={{
                            transform: analyticsOpen ? 'rotate(180deg)' : 'none',
                            transition: 'transform 0.2s',
                            color: 'var(--text-muted)',
                          }} />
                        )}
                      </div>
                      {analyticsOpen && !collapsed && (
                        <div style={{ paddingLeft: 26, marginTop: 2, display: 'flex', flexDirection: 'column', gap: 1 }}>
                          {item.children.map(child => (
                            <Link
                              key={child.href}
                              href={child.href as any}
                              className={`nav-item ${pathname === child.href ? 'active' : ''}`}
                              style={{ fontSize: '0.8rem', padding: '6px 10px' }}
                            >
                              {child.label}
                            </Link>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                }
                const isActive = pathname === item.href || (item.href !== '/home' && pathname.startsWith(item.href));
                return (
                  <Link
                    key={item.href}
                    href={item.href as any}
                    className={`nav-item ${isActive ? 'active' : ''}`}
                    style={{ justifyContent: collapsed ? 'center' : 'flex-start', position: 'relative' }}
                  >
                    <item.icon size={16} style={{ flexShrink: 0 }} />
                    {!collapsed && <span style={{ flex: 1 }}>{item.label}</span>}
                    {!collapsed && item.badge && (
                      <span style={{
                        background: 'var(--accent-red)', color: 'white',
                        borderRadius: 10, padding: '1px 6px',
                        fontSize: '0.6875rem', fontWeight: 700,
                      }}>{item.badge}</span>
                    )}
                  </Link>
                );
              })}
            </>
          )}

          {isSettings && (
            <>
              <Link
                href="/home"
                className="nav-item"
                style={{ marginBottom: 8, justifyContent: collapsed ? 'center' : 'flex-start' }}
              >
                <ChevronLeft size={16} style={{ flexShrink: 0 }} />
                {!collapsed && <span>Orqaga</span>}
              </Link>
              {!collapsed && <div className="section-title" style={{ marginBottom: 8 }}>Sozlamalar</div>}
              {SETTINGS_NAV.map(item => {
                const isActive = pathname === item.href || pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href as any}
                    className={`nav-item ${isActive ? 'active' : ''}`}
                    style={{ justifyContent: collapsed ? 'center' : 'flex-start' }}
                  >
                    <item.icon size={15} style={{ flexShrink: 0 }} />
                    {!collapsed && <span>{item.label}</span>}
                  </Link>
                );
              })}
            </>
          )}
        </nav>

        {/* Collapse toggle */}
        <div style={{ padding: '8px', borderTop: '1px solid var(--border)' }}>
          <button
            className="btn-icon"
            style={{ width: '100%', justifyContent: 'center' }}
            onClick={() => setCollapsed(v => !v)}
          >
            {collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
            {!collapsed && <span style={{ marginLeft: 8, fontSize: '0.8rem', color: 'var(--text-muted)' }}>Yig'ish</span>}
          </button>
        </div>
      </aside>

      {/* ── Main ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Header */}
        <header style={{
          height: 'var(--header-h)',
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          gap: 8,
          flexShrink: 0,
        }}>
          {/* Search */}
          <div style={{
            flex: 1,
            maxWidth: 320,
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
          }}>
            <Search size={14} style={{ position: 'absolute', left: 10, color: 'var(--text-muted)' }} />
            <input
              className="input"
              placeholder="Qidirish... (/)"
              style={{ paddingLeft: 32, height: 34, fontSize: '0.8125rem' }}
            />
          </div>

          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            {/* Notifications */}
            <div style={{ position: 'relative' }}>
              <button className="btn-icon" onClick={() => setNotifOpen(v => !v)} style={{ position: 'relative' }}>
                <Bell size={16} />
                <span style={{
                  position: 'absolute', top: 4, right: 4,
                  width: 7, height: 7, borderRadius: '50%',
                  background: 'var(--accent-red)',
                  border: '1px solid var(--bg-surface)',
                }} />
              </button>
              {notifOpen && (
                <div style={{
                  position: 'absolute', right: 0, top: '110%', width: 300, zIndex: 50,
                  background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                  borderRadius: 12, padding: 12,
                }}>
                  <div style={{ fontSize: '0.8125rem', fontWeight: 600, marginBottom: 8 }}>Bildirishnomalar</div>
                  {[
                    { text: 'Baxtiyorjon bugun qo\'ng\'iroq qilmadi', time: '17 soat oldin', type: 'amber' },
                    { text: 'Haftalik hisobot tayyor', time: '2 kun oldin', type: 'blue' },
                    { text: 'Yangi lid qo\'shildi', time: '3 kun oldin', type: 'green' },
                  ].map((n, i) => (
                    <div key={i} style={{
                      padding: '8px 0',
                      borderBottom: i < 2 ? '1px solid var(--border)' : 'none',
                    }}>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{n.text}</div>
                      <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginTop: 2 }}>{n.time}</div>
                    </div>
                  ))}
                  <Link href="/alerts" style={{ display: 'block', textAlign: 'center', marginTop: 8, fontSize: '0.8125rem', color: 'var(--accent)' }}>
                    Hammasini ko'rish →
                  </Link>
                </div>
              )}
            </div>

            {/* Bug report */}
            <button className="btn-icon" title="Xabar yuborish">
              <Bug size={15} />
            </button>

            {/* Business switcher */}
            <button className="btn-ghost" style={{ height: 34, gap: 6 }}>
              <Building2 size={14} />
              <span style={{ fontSize: '0.8125rem', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                Jon Branding
              </span>
              <ChevronDown size={12} style={{ color: 'var(--text-muted)' }} />
            </button>

            {/* Avatar */}
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setUserOpen(v => !v)}
                style={{
                  width: 34, height: 34, borderRadius: '50%',
                  background: 'linear-gradient(135deg, var(--accent), var(--accent-violet))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: 700, fontSize: '0.875rem', color: 'white',
                  border: 'none', cursor: 'pointer',
                }}
              >
                B
              </button>
              {userOpen && (
                <div style={{
                  position: 'absolute', right: 0, top: '110%', width: 220, zIndex: 50,
                  background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                  borderRadius: 12, padding: 8, overflow: 'hidden',
                }}>
                  <div style={{ padding: '8px 10px 12px', borderBottom: '1px solid var(--border)', marginBottom: 4 }}>
                    <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>Baxtiyorjon</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Rahbar · Jon Branding</div>
                  </div>
                  <Link href="/settings/profile" className="nav-item" style={{ gap: 8 }}>
                    <User size={14} /> Profil
                  </Link>
                  <Link href="/settings/general" className="nav-item" style={{ gap: 8 }}>
                    <Settings size={14} /> Sozlamalar
                  </Link>
                  <div style={{ margin: '4px 0', borderTop: '1px solid var(--border)' }} />
                  <button className="nav-item" style={{ width: '100%', color: 'var(--accent-red)' }}>
                    <LogOut size={14} /> Chiqish
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main style={{ flex: 1, overflow: 'auto' }}>
          {children}
        </main>
      </div>
    </div>
  );
}
