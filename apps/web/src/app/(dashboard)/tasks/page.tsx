import React from 'react';

export default function TasksDashboard() {
  const dummyTasks = [
    { id: 1, title: 'Oisha-OS yangi dizayni', assignee: 'Sardor', priority: 'High', status: 'In Progress', deadline: '2026-07-25' },
    { id: 2, type: 'AmoCRM integratsiyasi', assignee: 'Bekzod', priority: 'Medium', status: 'Todo', deadline: '2026-07-28' },
    { id: 3, type: 'Marketing video montaj', assignee: 'Madina', priority: 'High', status: 'Review', deadline: '2026-07-21' },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Vazifalar va Jamoa Yuklamasi</h1>
        <button className="rounded-xl bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 transition-colors">
          + Yangi Vazifa
        </button>
      </div>

      <div className="grid grid-cols-4 gap-6">
        <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm border-l-4 border-l-gray-300">
          <p className="text-sm font-medium text-gray-500">Qilinishi kerak (Todo)</p>
          <p className="mt-2 text-2xl font-bold text-gray-900">12</p>
        </div>
        <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm border-l-4 border-l-blue-500">
          <p className="text-sm font-medium text-gray-500">Jarayonda (In Progress)</p>
          <p className="mt-2 text-2xl font-bold text-gray-900">8</p>
        </div>
        <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm border-l-4 border-l-yellow-500">
          <p className="text-sm font-medium text-gray-500">Tekshiruvda (Review)</p>
          <p className="mt-2 text-2xl font-bold text-gray-900">3</p>
        </div>
        <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm border-l-4 border-l-green-500">
          <p className="text-sm font-medium text-gray-500">Bajarildi (Done)</p>
          <p className="mt-2 text-2xl font-bold text-gray-900">24</p>
        </div>
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-gray-100 px-6 py-4">
          <h2 className="font-semibold text-gray-900">Faol Vazifalar</h2>
        </div>
        <table className="w-full text-left text-sm text-gray-600">
          <thead className="bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="px-6 py-3">Vazifa nomi</th>
              <th className="px-6 py-3">Mas'ul xodim</th>
              <th className="px-6 py-3">Muhimlik</th>
              <th className="px-6 py-3">Holat</th>
              <th className="px-6 py-3">Muddat</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {dummyTasks.map((task) => (
              <tr key={task.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4 font-medium text-gray-900">{task.title || task.type}</td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-2">
                    <div className="h-6 w-6 rounded-full bg-purple-100 flex items-center justify-center text-xs text-purple-700 font-bold">
                      {task.assignee.charAt(0)}
                    </div>
                    <span>{task.assignee}</span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${
                    task.priority === 'High' ? 'bg-red-50 text-red-700 ring-red-600/10' :
                    task.priority === 'Medium' ? 'bg-yellow-50 text-yellow-800 ring-yellow-600/20' :
                    'bg-green-50 text-green-700 ring-green-600/20'
                  }`}>
                    {task.priority}
                  </span>
                </td>
                <td className="px-6 py-4 text-gray-500 font-medium">{task.status}</td>
                <td className="px-6 py-4 text-gray-500">{task.deadline}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
