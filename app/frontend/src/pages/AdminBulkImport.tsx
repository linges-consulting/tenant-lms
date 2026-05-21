import { useState, useRef, useEffect } from 'react';
import { Upload } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { userService } from '../api/users';
import { tenantService } from '../api/tenants';
import type { Tenant } from '../api/auth';

interface ImportSuccess {
  row: number;
  email: string;
}

interface ImportFailure {
  row: number;
  email: string;
  reason: string;
}

interface ImportResult {
  successes: ImportSuccess[];
  failures: ImportFailure[];
  total_rows: number;
}

export function AdminBulkImport() {
  const [tenantId, setTenantId] = useState('');
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    tenantService.list().then(setTenants).catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file || !tenantId) return;

    setIsLoading(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const data = await userService.bulkImport(tenantId, formData);
      setResult(data);
    } catch {
      setError('Import failed. Please check your CSV format.');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center shrink-0">
          <Upload className="w-6 h-6 text-violet-600 dark:text-violet-400" />
        </div>
        Bulk User Import
      </h1>
      <Card>
        <CardHeader>
          <CardTitle>Upload CSV</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm font-medium text-foreground block mb-1">
                Target Tenant
              </label>
              <Select value={tenantId} onValueChange={setTenantId} required>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select a tenant…" />
                </SelectTrigger>
                <SelectContent>
                  {tenants.map(t => (
                    <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium text-foreground block mb-1">
                CSV File{' '}
                <span className="ml-1 text-xs text-muted-foreground">
                  (columns: email, first_name, last_name, is_business_manager, is_training_creator)
                </span>
              </label>
              <input
                ref={fileRef}
                type="file"
                accept=".csv"
                required
                className="text-sm text-foreground"
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={isLoading || !tenantId}>
              {isLoading ? 'Importing…' : 'Import Users'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>
              Result: {result.successes.length} succeeded, {result.failures.length} failed
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {result.failures.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-destructive mb-2">Failures</h3>
                <div className="space-y-1">
                  {result.failures.map(f => (
                    <p key={f.row} className="text-sm text-muted-foreground">
                      Row {f.row} ({f.email}): {f.reason}
                    </p>
                  ))}
                </div>
              </div>
            )}
            {result.successes.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2">Successes</h3>
                <p className="text-sm text-muted-foreground">
                  {result.successes.map(s => s.email).join(', ')}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
